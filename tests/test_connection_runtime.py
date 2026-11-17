import uuid
import psycopg
from  ingestion.runtime import RunContext, run_pipeline
from ingestion.infra import create_connection, utc_now


if __name__ == "__main__":

    test_uuid = uuid.uuid4()
    print(test_uuid)

    def throw_con_err():
        raise psycopg.OperationalError("TEST_CONNECTION_FAILURE")

    def throw_pipeline_err(c: psycopg.Connection, r: RunContext):
        raise AssertionError("Pipeline must not be called")

    try:

        run_pipeline(
            name="Connection fail pipeline",
            connection_factory=throw_con_err,
            time_function=utc_now,
            uuid_gen=lambda: test_uuid,
            pipeline=throw_pipeline_err,
        )

    except psycopg.OperationalError as e:
        assert str(e) == "TEST_CONNECTION_FAILURE"

    else:
        raise AssertionError("No connection error")

    with create_connection() as conn:
        with conn.cursor() as curr:
            curr.execute(
                """SELECT
                    COUNT(*)
                    FROM ops.ingestion_runs
                WHERE ingestion_run_id=%s""", (test_uuid,)
            )
            r = curr.fetchone()
            assert r[0] == 0
    print("Connection test passed")
