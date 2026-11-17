import uuid

from ingestion.infra import create_connection, utc_now
from ingestion.runtime import run_pipeline
from ingestion.load_accounts import account_ingestion


def count_raw_accounts() -> int:
    with create_connection() as connection:
        with connection.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM raw.accounts")
            return cur.fetchone()[0]


def test_accounts_repeat() -> None:
    first_run_id = uuid.uuid4()
    second_run_id = uuid.uuid4()

    rows_before = count_raw_accounts()

    run_pipeline(
        name="test_accounts_repeat",
        connection_factory=create_connection,
        time_function=utc_now,
        uuid_gen=lambda: first_run_id,
        pipeline=account_ingestion,
    )

    rows_after_first = count_raw_accounts()

    run_pipeline(
        name="test_accounts_repeat",
        connection_factory=create_connection,
        time_function=utc_now,
        uuid_gen=lambda: second_run_id,
        pipeline=account_ingestion,
    )

    rows_after_second = count_raw_accounts()

    assert rows_after_second == rows_after_first, (
        "Repeated ingestion changed the RAW row count: "
        f"first={rows_after_first}, second={rows_after_second}"
    )

    with create_connection() as connection:
        with connection.cursor() as cur:
            cur.execute("""
                SELECT
                    ingestion_run_id,
                    run_status,
                    rows_read,
                    rows_saved,
                    rows_skipped,
                    error_cause
                FROM ops.ingestion_runs
                WHERE ingestion_run_id IN (%s, %s)
            """, (first_run_id, second_run_id))

            records = cur.fetchall()

    assert len(records) == 2, "Expected exactly two audit records"

    runs = {record[0]: record[1:] for record in records}

    first_status, first_read, first_saved, first_skipped, first_error = (
        runs[first_run_id]
    )
    second_status, second_read, second_saved, second_skipped, second_error = (
        runs[second_run_id]
    )

    assert first_status == "SUCCESS", "First run was not successful"
    assert second_status == "SUCCESS", "Second run was not successful"
    assert first_error is None
    assert second_error is None

    assert rows_after_first - rows_before == first_saved, (
        "First-run audit does not match the RAW row count change"
    )
    assert first_read == first_saved + first_skipped

    assert second_read == first_read, (
        "Source row count changed between runs"
    )
    assert second_saved == 0, "Repeated run saved new RAW versions"
    assert second_skipped == second_read, (
        "Repeated run did not skip every source row"
    )

    print(
        "Accounts repeat test passed: "
        f"first_saved={first_saved}, "
        f"second_saved={second_saved}, "
        f"second_skipped={second_skipped}"
    )


if __name__ == "__main__":
    test_accounts_repeat()