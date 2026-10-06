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
                    (SELECT COUNT(*) FROM raw.customers) AS raw_customer_version_count
            """)
            record = cur.fetchone()

            expected = (2, 2, 2, 2, 2)
            if record != expected:
                raise ValueError(
                    f"Unexpected counts: (source, raw, staging):"
                    f"expected {expected}, got {record}"
                )

    print(f"Pipeline check passed: {record}")

if __name__ == "__main__":
	check_pipeline()