import uuid
from datetime import datetime, timezone
from load_entries import with_connection

@with_connection
def account_ingestion(cnn):
    
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
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)""", (ingestion_run_id, "RUNNING", rows_read, rows_saved, rows_skipped, "source_accounts_to_raw", datetime.now(timezone.utc)))
        cnn.commit()
        try:
            cur.execute("""SELECT 
            account_id, 
            currency_id,
            customer_id,
            registered_at_dt,
            created_at_dt,
            updated_at_dt
            FROM source.accounts""")
            source_rows = cur.fetchall()
            rows_read = len(source_rows)

            for source_row in source_rows:
                source_account_id = source_row[0]
                cur.execute("""SELECT 
                account_id, 
                currency_id,
                customer_id,
                registered_at_dt,
                created_at_dt,
                updated_at_dt
                FROM raw.accounts 
                WHERE account_id = %s 
                ORDER BY account_version_id DESC 
                LIMIT 1""", (source_account_id, ))
                raw_row = cur.fetchone()
                if raw_row is not None and source_row[2] != raw_row[2]:
                    raise ValueError(
                        f"Account {source_account_id}: customer_id changed "
                        f"from {raw_row[2]} to {source_row[2]}"
                    )
                if raw_row is not None and source_row[1:4] == raw_row[1:4]:
                    rows_skipped += 1
                    continue
                # Here land all accounts new and changed
                cur.execute(
                    """INSERT INTO raw.accounts (
                        account_id, 
                        currency_id,
                        customer_id,
                        registered_at_dt,
                        created_at_dt,
                        updated_at_dt,
                        ingestion_run_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (*source_row, ingestion_run_id),
                )
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
    account_ingestion()