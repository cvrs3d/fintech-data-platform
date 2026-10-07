# Fintech Data Platform

## Project's purpose 

The purpose of this project is to create simple data platform for fintech DWH in order to get practice with modern techniques and technologies used in modern day development and analysis

## Current functionality

Created PostgreSQL (Source schema), atomic creation of transfers, testing of rollback. 
RAW layer and ingestion  developed.

dbt is initialized and working, users can now run from projects root directory

```bash
uv run --env-file .env dbt debug \
  --project-dir dbt \
  --profiles-dir dbt

uv run --env-file .env dbt build \
  --project-dir dbt \
  --profiles-dir dbt \
  --select stg_entries

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

    type `sudo docker compose up -d postgres`

    test `sudo docker compose exec postgres pg_isready -U {username} -d {dbname}`  wait for `accepting connections`

3) Configure schemas and tables inside the container from ./infra/sql ! This is one run only !
    1. Schema setup: type `sudo docker compose exec -T postgres psql -U {username} -d {dbname} -v ON_ERROR_STOP=1 --single-transaction < infra/sql/001_source_schema.sql`
    2. Demo data: type `sudo docker compose exec -T postgres psql -U {username} -d {dbname} -v ON_ERROR_STOP=1 < infra/sql/002_demo_data.sql`
    3. Alter tables: type `sudo docker compose exec -T postgres psql -U {username} -d {dbname} -v ON_ERROR_STOP=1 --single-transaction < infra/sql/003_entries_identifiers.sql`
    4. Alter tables: type `sudo docker compose exec -T postgres psql -U {username} -d {dbname} -v ON_ERROR_STOP=1 --single-transaction < infra/sql/004_transfer_requests.sql`
    5. Create raw layer entries: type `sudo docker compose exec -T postgres psql -U {username} -d {dbname} -v ON_ERROR_STOP=1 --single-transaction < infra/sql/005_raw_entries.sql`
    6. Create ops  `sudo docker compose exec -T postgres psql -U {username} -d {dbname} -v ON_ERROR_STOP=1 --single-transaction < infra/sql/006_ingestion_runs.sql`
    7. Create raw layer for customers `sudo docker compose exec -T postgres psql -U {username} -d {dbname} -v ON_ERROR_STOP=1 --single-transaction < infra/sql/007_raw_customers.sql`

4) Sync dependencies 
    `uv sync --locked` 

5) Test connection and demo entry 
    1. Connection: `uv run python generator/check_connection.py` output should be similar to this: `('fintech', 'postgres')`
    2. Create a demo transfer (every run creates new trnasfer) to check idempotency use same key for two consecutive runs: 

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
    3. Test idempotency 
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
    4. Ingest data into raw.entries 
    This command is idempotent 
    `uv run --locked python ingestion/load_entries.py`

    5. Ingest data into raw.customers
    This command is idempotent 
    `uv run --locked python ingestion/load_customers.py`

    6. Build staging entries and dim_customer with dbt 
    ```bash
    uv run --locked --env-file .env dbt build \
        --project-dir dbt \
        --profiles-dir dbt \
        --select stg_entries dim_customer
    ```