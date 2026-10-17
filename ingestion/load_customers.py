import uuid
from datetime import datetime, timezone
from load_entries import with_connection

@with_connection
def customer_ingestion(cnn):
    
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
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)""", (ingestion_run_id, "RUNNING", rows_read, rows_saved, rows_skipped, "source_customers_to_raw", datetime.now(timezone.utc)))
        cnn.commit()
        try:
            cur.execute("""SELECT
                customer_id,
                first_name,
                last_name,
                birth_date,
                death_date,
                registered_at_dt,
                updated_at_dt,
                created_at_dt,
                source_customer_version_id,
                effective_from_dt AS source_effective_from_dt
            FROM source.customer_history
            ORDER BY source_customer_version_id;"""
            )
            source_rows = cur.fetchall()
            rows_read = len(source_rows)

            for source_row in source_rows:
                cur.execute("""
                    SELECT 1
                    FROM raw.customers
                    WHERE source_customer_version_id = %s
                """, (source_row[8],))

                if cur.fetchone() is not None:
                    rows_skipped += 1
                    continue
                # Here land all clients new and changed
                cur.execute("""
                    INSERT INTO raw.customers (
                        customer_id,
                        first_name,
                        last_name,
                        birth_date,
                        death_date,
                        registered_at_dt,
                        updated_at_dt,
                        created_at_dt,
                        source_customer_version_id,
                        source_effective_from_dt,
                        ingestion_run_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (*source_row, ingestion_run_id))

                rows_saved += 1
            # Update ops. runs
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
    customer_ingestion()