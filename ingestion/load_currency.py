import uuid
from datetime import datetime, timezone
from load_entries import with_connection

@with_connection
def currency_ingestion(cnn):
    
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
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)""", (ingestion_run_id, "RUNNING", rows_read, rows_saved, rows_skipped, "source_currency_to_raw", datetime.now(timezone.utc)))
        cnn.commit()
        try:
            quarantine_record = None
            cur.execute("""
            SELECT 
            currency_id,
            currency_code,
            registered_at_dt,
            updated_at_dt,
            created_at_dt
            FROM source.currency
            """)
            source_rows = cur.fetchall()
            rows_read = len(source_rows)

            for source_row in source_rows:
                source_currency_id = source_row[0]
                cur.execute("""
                SELECT 
                currency_id,
                currency_code,
                registered_at_dt,
                updated_at_dt,
                created_at_dt
                FROM raw.currency 
                WHERE currency_id = %s 
                """, (source_currency_id, ))
                raw_row = cur.fetchone()
                if raw_row is not None and source_row[0:2] == raw_row[0:2]:
                    rows_skipped += 1
                    continue
                if raw_row is not None and raw_row[1] != source_row[1]:
                    error_msg = "CURRENCY_CODE_CHANGED"

                    quarantine_record = (
                        source_currency_id,
                        raw_row[1],      # код, уже сохранённый в RAW
                        source_row[1],   # входящий код
                        error_msg,
                        ingestion_run_id,
                    )

                    raise ValueError(
                        f"{error_msg}: currency_id={source_currency_id}, "
                        f"original={raw_row[1]}, incoming={source_row[1]}"
                    )
                
                cur.execute("""
                INSERT INTO raw.currency (
                currency_id,
                currency_code,
                registered_at_dt,
                updated_at_dt,
                created_at_dt,
                ingestion_run_id)
                VALUES (%s, %s, %s, %s, %s, %s)""", (*source_row, ingestion_run_id))
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

            if quarantine_record is not None:
                cur.execute("""
                    INSERT INTO quarantine.currency (
                        currency_id,
                        currency_original_code,
                        currency_incoming_code,
                        reason,
                        ingestion_run_id
                    )
                    VALUES (%s, %s, %s, %s, %s)
                """, quarantine_record)
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
    currency_ingestion()

