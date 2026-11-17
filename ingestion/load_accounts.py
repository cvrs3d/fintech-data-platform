import uuid
import psycopg
from  runtime import RunContext, run_pipeline
from infra import create_connection, utc_now


def account_ingestion(cnn: psycopg.Connection, context: RunContext) -> None:

    with cnn.cursor() as cur:
            cur.execute("""SELECT
                account_id,
                currency_id,
                customer_id,
                registered_at_dt,
                created_at_dt,
                updated_at_dt,
                source_account_version_id,
                effective_from_dt AS source_effective_from_dt
            FROM source.account_history
            ORDER BY source_account_version_id""")
            source_rows = cur.fetchall()
            context.stats.rows_read = len(source_rows)

            for source_row in source_rows:
                # mocking updated row
                # `if source_row[0] == 1:
                #     mock_row = list(source_row)
                #     mock_row[3] += timedelta(days=1) # registred at
                #     mock_row[5] = datetime.now(timezone.utc) #updated_at
                #     source_row = tuple(mock_row)
                cur.execute("""
                SELECT 1
                FROM raw.accounts
                WHERE source_account_version_id = %s;
                """, (source_row[6],),
                )
                if cur.fetchone() is not None: 
                    context.stats.rows_skipped += 1
                    continue
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
                # Here land all accounts new and changed
                cur.execute(
                """
                INSERT INTO raw.accounts (
                    account_id,
                    currency_id,
                    customer_id,
                    registered_at_dt,
                    created_at_dt,
                    updated_at_dt,
                    source_account_version_id,
                    source_effective_from_dt,
                    ingestion_run_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (*source_row, context.ingestion_run_id),
                )
                context.stats.rows_saved += 1


if __name__ == "__main__":
    run_pipeline(
        name="source_accounts_to_raw",
        connection_factory=create_connection,
        time_function=utc_now,
        uuid_gen=uuid.uuid4,
        pipeline=account_ingestion
    )