from datetime import datetime, timedelta, timezone

from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator


with DAG(
    dag_id="fintech_batch",
    start_date=datetime(2026, 10, 18, tzinfo=timezone.utc),
    schedule="@hourly",
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=1),
        "execution_timeout": timedelta(minutes=10),
    },
    tags=["fintech", "batch"],
) as dag:

    load_currency = BashOperator(
        task_id="load_currency",
        bash_command=(
            "/opt/fintech/.venv/bin/python ingestion/load_currency.py"
        ),
        cwd="/opt/fintech",
        do_xcom_push=False,
    )

    load_customers = BashOperator(
        task_id="load_customers",
        bash_command=(
            "/opt/fintech/.venv/bin/python ingestion/load_customers.py"
        ),
        cwd="/opt/fintech",
        do_xcom_push=False,
    )

    load_accounts = BashOperator(
        task_id="load_accounts",
        bash_command=(
            "/opt/fintech/.venv/bin/python ingestion/load_accounts.py"
        ),
        cwd="/opt/fintech",
        do_xcom_push=False,
    )

    load_entries = BashOperator(
        task_id="load_entries",
        bash_command=(
            "/opt/fintech/.venv/bin/python ingestion/load_entries.py"
        ),
        cwd="/opt/fintech",
        do_xcom_push=False,
    )

    build_marts = BashOperator(
        task_id="build_marts",
        bash_command=(
            "/opt/fintech/.venv/bin/dbt build --project-dir dbt --profiles-dir dbt --select +mart_account_daily"
        ),
        cwd="/opt/fintech",
        do_xcom_push=False,
    )

    load_currency >> load_customers >> load_accounts >> load_entries >> build_marts