import uuid
import psycopg
from  ingestion.runtime import RunContext, run_pipeline
from ingestion.infra import create_connection, utc_now


def insert_account_then_fail(cnn: psycopg.Connection, context: RunContext) -> None:
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
            source_row = cur.fetchone()
            assert source_row is not None
            insert_params = (*source_row[0:6], None, source_row[7], context.ingestion_run_id)
            context.stats.rows_read = 1

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
            (*insert_params,),
            )
            if cur.rowcount != 1:
                 raise RuntimeError("TEST_FAILURE_ROW_COUNT_NOT_1")
            context.stats.rows_saved += 1
            raise RuntimeError("TEST_FAILURE_AFTER_INSERT")

if __name__ == "__main__":
    test_run_id = uuid.uuid4()
    print(test_run_id )
    try:
        run_pipeline(
            name="test_account_ingestion",
            connection_factory=create_connection,
            time_function=utc_now,
            uuid_gen=lambda : test_run_id ,
            pipeline=insert_account_then_fail)
    except RuntimeError as e:
        assert str(e) == "TEST_FAILURE_AFTER_INSERT"
    else:
        raise AssertionError
    with create_connection() as conn:
        with conn.cursor() as curr:
            curr.execute("""SELECT
                COUNT(*)
            FROM raw.accounts
            WHERE ingestion_run_id=%s""", (test_run_id,))
            source_row = curr.fetchone()
            assert source_row is not None
            assert source_row[0] == 0
            curr.execute("""SELECT
                run_status,
                rows_read,
                rows_saved,
                error_cause
            FROM ops.ingestion_runs
            WHERE ingestion_run_id=%s""", (test_run_id,))
            source_row = curr.fetchall()
            assert source_row is not None
            assert source_row == [("FAILED", 1, 0, "TEST_FAILURE_AFTER_INSERT")]
    print("Rollback test passed")
