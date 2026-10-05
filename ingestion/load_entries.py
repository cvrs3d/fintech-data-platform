import psycopg
import os 
import dotenv 
import uuid
from datetime import datetime, timezone

def with_connection(f):
    def with_connection_(*args, **kwargs):
        dotenv.load_dotenv()
        dbname = os.environ["POSTGRES_DB"]
        user = os.environ["POSTGRES_USER"]
        password = os.environ["POSTGRES_PASSWORD"]

        cnn = psycopg.connect(
            host="127.0.0.1",
            port=5432,
            dbname=dbname,
            user=user,
            password=password,
            connect_timeout=5,
        )
        try:
            return f(cnn, *args, **kwargs)
        finally:
            cnn.close()

    return with_connection_

@with_connection
def ingestion(cnn):
    
    ingestion_run_id = uuid.uuid4()
    rows_read = 0
    rows_skipped = 0
    rows_saved = 0

    with cnn.cursor() as cur:
        cur.execute("""INSERT INTO ops.ingestion_runs (
            ingestion_run_id,
            run_status, 
            rows_read, 
            rows_saved, 
            rows_skipped, 
            pipeline_name, 
            start_time_dt
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)""", (ingestion_run_id, "RUNNING", rows_read, rows_saved, rows_skipped, "load_entries.py", datetime.now(timezone.utc)))
        cnn.commit()
        try:
            cur.execute("SELECT entry_id, transaction_id, account_id, amount, created_at_dt, executed_at_dt FROM source.entries")
            source_rows = cur.fetchall()
            rows_read = len(source_rows)

            for source_row in source_rows:
                source_entry_id = source_row[0]
                cur.execute("SELECT entry_id, transaction_id, account_id, amount, created_at_dt, executed_at_dt FROM raw.entries WHERE entry_id=%s", (source_entry_id,))
                raw_row = cur.fetchone()

                if raw_row is None:
                    cur.execute(
                        """
                        INSERT INTO raw.entries (
                            entry_id,
                            transaction_id,
                            account_id,
                            amount,
                            created_at_dt,
                            executed_at_dt,
                            ingestion_run_id
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (*source_row, ingestion_run_id),
                    )
                    rows_saved += 1
                elif source_row == raw_row:
                    # Same data
                    rows_skipped += 1
                    continue
                else:
                    raise ValueError(f"Conflicting entry. Entry ID: {source_entry_id}")
            # Update
            cur.execute(
                """
                UPDATE ops.ingestion_runs
                SET run_status = 'SUCCESS',
                    rows_read = %s,
                    rows_saved = %s,
                    rows_skipped = %s,
                    end_time_dt = %s
                WHERE ingestion_run_id = %s
                """,
                (
                    rows_read,
                    rows_saved,
                    rows_skipped,
                    datetime.now(timezone.utc),
                    ingestion_run_id,
                ),
            )
            cnn.commit()
        except Exception as error:
            cnn.rollback()
            cur.execute("""UPDATE ops.ingestion_runs 
            SET run_status = 'FAILED', 
            rows_saved = 0,
            rows_skipped = %s,
            rows_read = %s,
            end_time_dt = %s,
            error_cause = %s
            WHERE ingestion_run_id = %s""", (rows_skipped, rows_read, datetime.now(timezone.utc), str(error), ingestion_run_id,))
            cnn.commit()
            raise 


if __name__ == "__main__":
    ingestion()



