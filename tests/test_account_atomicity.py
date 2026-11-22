import uuid

import pytest

from ingestion import load_accounts as accounts
from ingestion.infra import create_connection, utc_now
from ingestion.runtime import run_pipeline


def seed(owners):
    with create_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany("""
                INSERT INTO source.account_history
                    (account_id, currency_id, customer_id, registered_at_dt,
                     created_at_dt, updated_at_dt, effective_from_dt)
                VALUES (1, 1, %s, current_date, now(), now(), now())
            """, [(owner,) for owner in owners])


def run(run_id, pipeline=accounts.account_ingestion):
    run_pipeline("test_accounts", create_connection, utc_now, lambda: run_id, pipeline)


def state(run_id):
    with create_connection() as conn:
        return conn.execute("""
            SELECT run_status, rows_read, rows_saved, rows_skipped, error_cause,
                   (SELECT count(*) FROM raw.accounts WHERE ingestion_run_id = %s)
            FROM ops.ingestion_runs WHERE ingestion_run_id = %s
        """, (run_id, run_id)).fetchone()


def test_empty_source():
    run_id = uuid.uuid4()
    run(run_id)
    assert state(run_id) == ("SUCCESS", 0, 0, 0, None, 0)


def test_failure_after_three_raw_inserts():
    seed([7, 7, 7])
    run_id = uuid.uuid4()

    def fail_before_commit(conn, context):
        accounts.account_ingestion(conn, context)
        assert conn.execute(
            "SELECT count(*) FROM raw.accounts WHERE ingestion_run_id = %s", (run_id,)
        ).fetchone() == (3,)
        raise RuntimeError("after three inserts")

    with pytest.raises(RuntimeError, match="after three inserts"):
        run(run_id, fail_before_commit)
    assert state(run_id) == ("FAILED", 3, 0, 0, "after three inserts", 0)


@pytest.mark.parametrize("existing, batch_size", [(False, 256), (False, 1), (True, 256)])
def test_owner_conflict(existing, batch_size, monkeypatch):
    monkeypatch.setattr(accounts, "BATCH_SIZE", batch_size)
    seed([7])
    if existing:
        first = uuid.uuid4()
        run(first)
    seed([9])
    run_id = uuid.uuid4()
    message = "Account 1: customer_id changed from 7 to 9"
    with pytest.raises(ValueError, match=message):
        run(run_id)
    assert state(run_id) == ("FAILED", 2, 0, int(existing), message, 0)
    with create_connection() as conn:
        assert conn.execute("SELECT customer_id FROM raw.accounts").fetchall() == (
            [(7,)] if existing else []
        )
