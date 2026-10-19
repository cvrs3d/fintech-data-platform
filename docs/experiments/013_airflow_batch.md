# Airflow batch orchestration

## Purpose

Run the existing ingestion and dbt pipeline through one DAG, `fintech_batch`.
The first manual run completed all five tasks successfully on the development
VM. Subsequent validation confirmed scheduled runs and automatic task retries.
The retry exercise exposed an API database connection-pool limit; the API pool
was increased, and the repeated exercise completed the loader on attempt 2.

## Runtime layout

The base [Compose file](../../docker-compose.yml) continues to manage PostgreSQL.
The [Airflow overlay](../../docker-compose.airflow.yml) adds these services:

| Service | Responsibility |
| --- | --- |
| `airflow-init` | Apply Airflow metadata migrations, then exit |
| `airflow-api-server` | Serve the UI and execution API |
| `airflow-scheduler` | Schedule work and run tasks using LocalExecutor |
| `airflow-dag-processor` | Parse DAG definitions |

The existing `fintech` database holds business and warehouse data. A separate
`airflow` database, owned by the `airflow` role, holds orchestration metadata in
the same PostgreSQL container. Only the scheduler receives the business database
credentials because LocalExecutor runs pipeline commands there.

The [Dockerfile](../../infra/airflow/Dockerfile) uses
`apache/airflow:3.3.2-python3.13` and uv `0.12.23`. It installs the locked project
dependencies in `/opt/fintech/.venv`, separately from Airflow's environment.
The verified image contains dbt Core `1.12.5` and dbt-postgres `1.11.0`.

The API server overrides the shared metadata database pool settings with
`AIRFLOW__DATABASE__SQL_ALCHEMY_POOL_SIZE=5` and
`AIRFLOW__DATABASE__SQL_ALCHEMY_MAX_OVERFLOW=10`. This permits up to 15 concurrent
connections per pool. Other services retain the shared limits of 2 and 1.
The API's environment block merges `*airflow-environment` before overriding
these two values, preserving the shared database and authentication settings.

Connection settings support both host and container execution:

| Setting | Commands on the VM | Airflow tasks |
| --- | --- | --- |
| `POSTGRES_HOST` | `127.0.0.1` by default | `postgres` |
| `POSTGRES_PORT` | `5432` by default | `5432` |
| Project directory | Repository root | `/opt/fintech` |
| Python/dbt environment | Project `.venv` | `/opt/fintech/.venv` |

The shared ingestion connection wrapper and dbt profile read the host and port
from environment variables. Compose supplies these variables to the scheduler;
pipeline commands inside the container do not need a copied `.env` file.

## One-time setup

Start from the [README setup](../../README.md#setup): initialize the business
database and run `uv sync --locked`. Run the commands below from the repository
root on the VM. They use `sudo docker`, as required by the development VM.

If Airflow is already configured, keep its database and secrets and continue
with the startup section. Do not repeat the role/database creation commands.

### Create the metadata database

Generate a password and save it as `AIRFLOW_DB_PASSWORD` in `.env`:

```bash
uv run --locked python -c 'import secrets; print(secrets.token_hex(24))'
sudo docker compose exec postgres psql -U postgres -d postgres
```

In psql, run:

```sql
CREATE ROLE airflow LOGIN;
CREATE DATABASE airflow OWNER airflow;
\password airflow
```

Enter the generated password twice when `\password` prompts for it. The value
must match `.env`, then use `\q` to exit psql. Use the generated hexadecimal
value: the overlay interpolates it directly into the metadata database
connection URL.

These commands assume the development superuser is `postgres`; substitute your
configured PostgreSQL superuser if different. Database creation is a separate
bootstrap step, outside the transactional business migrations in `infra/sql`.

### Configure environment variables

Keep the existing business database credentials and add these settings to `.env`:

```dotenv
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
AIRFLOW_DB_PASSWORD=replace_with_the_password_created_above
AIRFLOW_JWT_SECRET=
AIRFLOW_API_SECRET_KEY=
AIRFLOW_FERNET_KEY=
```

Generate the three application secrets. This script fills empty values or
`replace_with_...` placeholders and preserves existing real keys:

```bash
uv run --locked python - <<'PY'
from base64 import urlsafe_b64encode
from pathlib import Path
from secrets import token_bytes, token_hex

from dotenv import dotenv_values, set_key

path = Path(".env")
existing = dotenv_values(path)
keys = {
    "AIRFLOW_JWT_SECRET": token_hex(32),
    "AIRFLOW_API_SECRET_KEY": token_hex(32),
    "AIRFLOW_FERNET_KEY": urlsafe_b64encode(token_bytes(32)).decode(),
}
for name, value in keys.items():
    current = existing.get(name) or ""
    if not current or current.startswith("replace_with_"):
        set_key(str(path), name, value, quote_mode="never")
        print(f"Created: {name}")
path.chmod(0o600)
PY
```

Store only placeholders in `.env.example`. The project's `.gitignore` excludes
`.env`; `.dockerignore` also keeps environment files out of the image build
context. Keep real keys across container rebuilds.

## Start Airflow

Define this helper in each new shell session:

```bash
dc_airflow() {
  sudo docker compose --env-file .env \
    -f docker-compose.yml \
    -f docker-compose.airflow.yml "$@"
}
```

Validate the combined configuration, build the shared image and start services:

```bash
mkdir -p dags
chmod 755 dags

dc_airflow config --quiet &&
dc_airflow build airflow-init &&
dc_airflow up -d --wait --wait-timeout 180 \
  airflow-api-server airflow-scheduler airflow-dag-processor

dc_airflow ps -a
sudo docker stats --no-stream
```

`airflow-init` should exit with code 0. The API server, scheduler and DAG processor
should become healthy. The configuration limits task parallelism, API workers
and DAG parsing processes to one for the small development VM.

Named volumes preserve task logs and the SimpleAuthManager password file. The
metadata database remains in the existing PostgreSQL data volume. The local
`dags` directory is mounted read-only into Airflow containers.

## Open the UI

On your local computer, start an SSH tunnel to the VM:

```bash
ssh -N -L 8080:127.0.0.1:8080 dev@YOUR_VM_IP
```

Keep this terminal open. A silent session is expected with `-N`. Open
<http://127.0.0.1:8080> in your local browser.

The development setup uses SimpleAuthManager. The username is `admin`; retrieve
its generated password on the VM:

```bash
dc_airflow exec airflow-api-server \
  cat /opt/airflow/config/simple_auth_manager_passwords.json
```

The API port is bound to the VM's loopback interface. This configuration provides
development access through the tunnel; it is not a public Airflow deployment.

## DAG behavior

The [DAG](../../dags/fintech_batch.py) runs these tasks in order:

1. `load_currency`
2. `load_customers`
3. `load_accounts`
4. `load_entries`
5. `build_marts`

Each BashOperator uses `cwd="/opt/fintech"` and an absolute executable path in
`/opt/fintech/.venv`. The final task runs:

```bash
/opt/fintech/.venv/bin/dbt build \
  --project-dir dbt \
  --profiles-dir dbt \
  --select +mart_account_daily
```

The `+` selects the mart and its model dependencies. dbt also runs the selected
data and unit tests. A failed upstream task prevents downstream execution under
the default `all_success` trigger rule.

New DAGs start paused. For initial validation, use `schedule=None`, enable the
DAG in the UI and trigger a manual run. After all tasks succeed, set
`schedule="@hourly"` to enable the hourly schedule in UTC. No image rebuild is
needed for this DAG edit; wait for the DAG processor to pick it up.

The DAG uses `catchup=False`, `max_active_runs=1`, two retries with a one-minute
delay and a ten-minute timeout per task attempt. Two retries allow up to three
attempts. These limits control Airflow execution; they do not prevent someone
from starting a loader separately on the VM.

Every ingestion task still scans its source table. Existing entry IDs or source
version IDs are skipped; currency keeps its fixed-reference validation. The DAG
does not pass a date window to the loaders, so an hourly schedule is not an
incremental extraction strategy and historical backfills are not implemented.

Each loader invocation that reaches audit logging creates its own
`ops.ingestion_runs` record with a new run ID. A task failure before the loader
starts does not create a failed ingestion record; its evidence is in Airflow's
logs and task state.
The complete DAG is not one database transaction: earlier successful loader
commits remain if a later task fails. Existing loader rollback, quarantine and
deduplication behavior still applies.

## Update or stop services

Ingestion code, dbt files and project dependencies are copied into the image.
After changing them, rebuild and recreate the running services:

```bash
dc_airflow build airflow-init &&
dc_airflow up -d --wait --wait-timeout 180 \
  airflow-api-server airflow-scheduler airflow-dag-processor
```

Stop just Airflow while leaving PostgreSQL and its data available:

```bash
dc_airflow stop airflow-api-server airflow-scheduler airflow-dag-processor
```

## Validation and CI scope

Verified on the development VM:

- The image reports Airflow `3.3.2`, dbt Core `1.12.5` and dbt-postgres `1.11.0`.
- The metadata database exists with `airflow` as its owner.
- Initialization exits successfully and all three long-running Airflow services
  report healthy.
- The first manual `fintech_batch` run completes all five tasks successfully.
- By the morning of 2026-10-19, 19 successful scheduled runs were reported.
- An injected task failure is retried automatically. After the API pool change,
  `load_customers` completes on attempt 2 with exit code 0.

The VM has an ARM64 CPU and approximately 3.7 GiB of RAM. The three Airflow
services used approximately 650 MiB combined in the initial idle sample, before
the API pool adjustment. Peak memory during task execution has not been measured.

[CI](../../.github/workflows/ci.yml) validates the combined Compose configuration
using public test values, then runs the existing batch pipeline against a fresh
PostgreSQL database. It does not build the Airflow image or start an Airflow DAG.
Scheduled execution and task retry behavior were checked on the VM; these checks
are not automated in CI.

`tests/check_pipeline.py` expects the clean CI fixture and exactly two customer
and account ingestion runs. It is not a DAG task and is not a general health
check for the development database after repeated Airflow runs.

### Retry exercise and API pool adjustment: 2026-10-19

For the exercise, `load_customers` temporarily used a Boolean DAG parameter,
`test_fail_once`, defaulting to `False`. A manual run set it to `True`; a Bash
guard exited with code 1 only when `ti.try_number == 1`. Later attempts ran the
normal ingestion command. Scheduled runs kept the default parameter value.

The first test run was
`manual__2026-10-19T07:49:32.849737+00:00`. Attempt 2 contained only a
`Pre Execute` message in its task log. The scheduler log showed an
`httpx.ReadTimeout` while registering the task start with the Execution API,
followed by `UP_FOR_RETRY`. The API log also contained HTTP 500 responses and:

```text
QueuePool limit of size 2 overflow 1 reached,
connection timed out, timeout 30.00
```

Pool exhaustion was the likely cause of the API delays; these logs do not show
which requests held all the connections. Attempt 3 completed successfully, and
the full DAG run was reported successful. Scheduler logs show that
`load_accounts` started after `load_customers` succeeded.

The API service's pool was then increased from 2 + 1 to 5 + 10, preserving the
other shared environment settings. Applying this Compose change requires
recreating the API container after active runs finish; the pipeline image does
not need rebuilding.

In the new test run, `manual__2026-10-19T09:21:05.634858+00:00`,
`load_customers` completed on attempt 2 at 09:22:13 UTC with exit code 0.
The repeated test therefore achieved the expected task retry outcome after the
configuration change.

The injected failure happens before Python starts. It validates Airflow retry
and dependency handling, but does not exercise rollback after partial database
writes. Ingestion transaction behavior is a separate check. Remove the temporary
parameter and Bash guard after the exercise, retaining the normal retry settings
and the API pool override.

## References

- [Airflow Docker setup](https://airflow.apache.org/docs/apache-airflow/3.3.2/howto/docker-compose/index.html)
- [LocalExecutor](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/executor/local.html)
- [SimpleAuthManager](https://airflow.apache.org/docs/apache-airflow/3.3.2/core-concepts/auth-manager/simple/index.html)
- [Airflow database setup](https://airflow.apache.org/docs/apache-airflow/3.3.2/howto/set-up-database.html)
- [Airflow configuration reference](https://airflow.apache.org/docs/apache-airflow/3.3.2/configurations-ref.html)
