import uuid

from ingestion.infra import create_connection, utc_now
from ingestion.load_accounts import account_ingestion
from ingestion.runtime import run_pipeline


def test_accounts_repeat(one_account_version: int) -> None:
    first_id, second_id = uuid.uuid4(), uuid.uuid4()

    def raw_versions():
        with create_connection() as conn:
            return conn.execute("""
                SELECT source_account_version_id, ingestion_run_id
                FROM raw.accounts
            """).fetchall()

    assert raw_versions() == []

    for run_id, expected_counts in (
        (first_id, (1, 1, 0)),
        (second_id, (1, 0, 1)),
    ):
        run_pipeline(
            name="test_accounts_repeat",
            connection_factory=create_connection,
            time_function=utc_now,
            uuid_gen=lambda run_id=run_id: run_id,
            pipeline=account_ingestion,
        )

        with create_connection() as conn:
            audit = conn.execute("""
                SELECT run_status, rows_read, rows_saved, rows_skipped, error_cause
                FROM ops.ingestion_runs
                WHERE ingestion_run_id = %s
            """, (run_id,)).fetchall()

        assert audit == [("SUCCESS", *expected_counts, None)]
        assert raw_versions() == [(one_account_version, first_id)]
