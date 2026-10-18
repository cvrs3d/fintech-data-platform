# Fintech Data Platform

## Project's purpose 

The purpose of this project is to create simple data platform for fintech DWH in order to get practice with modern techniques and technologies used in modern day development and analysis

## Current functionality

PostgreSQL source tables support atomic transfers and transfer idempotency.
Python batch loaders populate RAW and track run status and counters in
`ops.ingestion_runs`.

Customer and account triggers capture source history. Their loaders ingest each
source version once, and dbt builds SCD2 dimensions using source effective time.
Initial snapshots establish the start of known history; they do not reconstruct
earlier states. Legacy RAW versions are retained but excluded from these
dimensions.

The currency loader maintains a fixed reference table. A changed code for an
existing currency ID fails the run and is recorded in quarantine.

dbt builds `stg_entries`, `dim_customer`, `dim_account`, `dim_currency` and
`fact_entries`. The fact retains one row per entry and resolves account and
customer versions at `executed_at_dt`. Entries without matching history remain
in the fact with unresolved dimension keys.

See [Source history for customers and accounts](docs/experiments/010_source_history.md)
for the versioning contract and
[Fact entries and temporal dimension joins](docs/experiments/011_fact_entries.md)
for the fact model, missing-history behavior and validation results.

Run from the project root:

```bash
uv run --locked --env-file .env dbt debug \
  --project-dir dbt \
  --profiles-dir dbt

uv run --locked --env-file .env dbt build \
  --project-dir dbt \
  --profiles-dir dbt \
  --select +fact_entries
```

## TODO
Airflow DAGs, orchestration, time-driven ingestion


## Setup

0)  Install dependecies: Git, Docker Engine with Compose, uv, python3.13
    Clone the repository then `cd fintech-data-platform/`
    Run `cp .env.example .env` then  `chmod 600 .env`


1) Fill in the .env: 
    POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD 

2) Deploy PostgreSQL container via compose 

    {username} and {dbname} must be similar with .env variables

    type `docker compose up -d postgres`

    test `docker compose exec -T postgres pg_isready -U {username} -d {dbname}` and wait for `accepting connections`

3) Configure schemas and tables inside the container from `infra/sql` (run once for a fresh database)
    ```bash
    set -a; source .env; set +a
    (
      set -e
      for file in infra/sql/*.sql; do
        docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 --single-transaction < "$file"
      done
    )
    ```

4) Sync dependencies 
    `uv sync --locked` 

5) Test connection and demo entry 
    1. Connection: `uv run --locked python generator/check_connection.py` output should be similar to this: `('fintech', 'postgres')`
    2. Ingest data into raw.entries 
    This command is idempotent 
    `uv run --locked python ingestion/load_entries.py`

    3. Ingest data into raw.customers
    This command is idempotent (run twice to verify) 
    `uv run --locked python ingestion/load_customers.py`
    `uv run --locked python ingestion/load_customers.py`

    4. Ingest data into raw.accounts
    This command is idempotent (run twice to verify) 
    `uv run --locked python ingestion/load_accounts.py`
    `uv run --locked python ingestion/load_accounts.py`

    5. Ingest data into currency 
    ```bash
    uv run --locked python ingestion/load_currency.py
    uv run --locked python ingestion/load_currency.py
    ```

    6. Build staging entries, dimensions and fact with dbt
    ```bash
    uv run --locked --env-file .env dbt build \
        --project-dir dbt \
        --profiles-dir dbt \
        --select +fact_entries
    ```
    7. Validate row counts and ingestion run counters (clean pipeline check)
    `uv run --locked python tests/check_pipeline.py`

    This check expects a fresh database and exactly two customer and account
    loader runs, as shown above. Additional historical versions or ingestion
    runs on a development database will change the expected results.

    8. Create a demo transfer (every run creates a new transfer):
    ```bash
    uv run python -c '
    from decimal import Decimal
    from generator.transfer import create_transfer

    from uuid import uuid4

    key = uuid4()
    transaction_id = create_transfer(1, 2, Decimal("25.00"), key)
    print(transaction_id)
    '
    ```

    8. Test transfer idempotency with the same key:
    ```bash
    uv run python - <<'PY'
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from decimal import Decimal
    from uuid import uuid4
    from generator.transfer import create_transfer

    key = uuid4()
    barrier = Barrier(2)

    def worker():
        barrier.wait(timeout=10)
        return create_transfer(1, 2, Decimal("17.00"), key)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker) for _ in range(2)]
        results = [future.result() for future in futures]

    print("Idempotency key:", key)
    print("Transactions:", results)

    assert results[0] == results[1], "Created different transfers!"
    print("Both calls returned the same transaction")
    PY
    ```
