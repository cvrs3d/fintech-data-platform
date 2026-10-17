import psycopg
import dotenv
import os

def check_pipeline():
    dotenv.load_dotenv()

    dbname = os.environ["POSTGRES_DB"]
    user = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]

    
    with psycopg.connect(
        host="127.0.0.1",
        port=5432,
        dbname=dbname,
        user=user,
        password=password,
        connect_timeout=5,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    (SELECT COUNT(*) FROM source.entries) AS source_count,
                    (SELECT COUNT(*) FROM raw.entries) AS raw_count,
                    (SELECT COUNT(*) FROM staging.stg_entries) AS staging_count,
                    (SELECT COUNT(*) FROM source.customers) AS source_customer_count,
                    (SELECT COUNT(*) FROM raw.customers) AS raw_customer_version_count,
                    (SELECT COUNT(*) FROM staging.dim_customer) AS dim_customer_count,
                    (SELECT COUNT(*) FROM source.accounts) AS source_account_count,
                    (SELECT COUNT(*) FROM raw.accounts) AS raw_account_version_count,
                    (SELECT COUNT(*) FROM staging.dim_account) AS dim_account_count,
                    (SELECT COUNT(*) FROM source.currency) AS source_currency_count,
                    (SELECT COUNT(*) FROM raw.currency) AS raw_currency_count,
                    (SELECT COUNT(*) FROM staging.dim_currency) AS dim_currency_count,
                    (SELECT COUNT(*) FROM source.account_history) AS source_account_history_count,
                    (SELECT COUNT(*) FROM source.customer_history) AS source_customer_history_count
            """)
            record = cur.fetchone()

            expected = (
                2, 2, 2,  # entries: source, raw, staging
                2, 2, 2,  # customers: source, raw, dimension
                2, 2, 2,  # accounts: source, raw, dimension
                1, 1, 1,  # currency: source, raw, dimension
                2,        # source.account_history
                2,        # source.customer_history
            )
            if record != expected:
                raise ValueError(
                    "Unexpected row counts "
                    "(source.entries, raw.entries, staging.stg_entries, "
                    "source.customers, raw.customers, staging.dim_customer, "
                    "source.accounts, raw.accounts, staging.dim_account,"
                    "source.currency, raw.currency, staging.dim_currency, "
                    "source.account_history, source.customer_history): "
                    f"expected={expected}, actual={record}"
                )
            expected_runs = [
                ("SUCCESS", 2, 2, 0),  # первая загрузка
                ("SUCCESS", 2, 0, 2),  # повторная загрузка
            ]

            for pipeline_name in (
                "source_customers_to_raw",
                "source_accounts_to_raw",
            ):
                cur.execute("""
                    SELECT
                        run_status,
                        rows_read,
                        rows_saved,
                        rows_skipped
                    FROM ops.ingestion_runs
                    WHERE pipeline_name = %s
                    ORDER BY start_time_dt
                """, (pipeline_name,))

                actual_runs = cur.fetchall()

                if actual_runs != expected_runs:
                    raise ValueError(
                        f"Unexpected ingestion runs for {pipeline_name}: "
                        f"expected={expected_runs}, actual={actual_runs}"
                    )

    print(f"Pipeline check passed: {record}")

if __name__ == "__main__":
	check_pipeline()