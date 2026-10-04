# Fintech Data Platform

## Project's purpose 

The purpose of this project is to create simple data platform for fintech DWH in order to get practice with modern techniques and technologies used in modern day development and analysis

## Current functionality

Created PostgreSQL (Source schema), atomic creation of transfers, testing of rollback. !RAW, dbt, Airflow are not done yet!

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

4) Sync dependencies 
    `uv sync --locked` 

5) Test connection and demo entry 
    1. Connection: `uv run python generator/check_connection.py` output should be similar to this: `('fintech', 'postgres')`
    2. Create a demo transfer (every run creates new trnasfer): 

    ```bash
    uv run python -c '
    from decimal import Decimal
    from generator.transfer import create_transfer

    transaction_id = create_transfer(1, 2, Decimal("25.00"))
    print(transaction_id)
    '
    ```