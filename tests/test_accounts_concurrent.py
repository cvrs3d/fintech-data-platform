import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor

from ingestion.infra import create_connection, utc_now
from ingestion.load_accounts import account_ingestion
from ingestion.runtime import run_pipeline


def test_second_worker_waits_then_skips(one_account_version, monkeypatch):
    monkeypatch.setenv(
        "PGOPTIONS",
        "-c default_transaction_isolation=read\\ committed -c statement_timeout=15000",
    )
    first, second = uuid.uuid4(), uuid.uuid4()
    b_pid = Future()

    def run(run_id, loader):
        run_pipeline("test_accounts_concurrent", create_connection, utc_now,
                     lambda: run_id, loader)

    def load_b(conn, context):
        # RUNNING has committed; tell A which independent backend to observe.
        b_pid.set_result(conn.info.backend_pid)
        account_ingestion(conn, context)

    with ThreadPoolExecutor(max_workers=1) as pool:
        def load_a(conn, context):
            nonlocal worker_b
            account_ingestion(conn, context)
            assert context.stats.rows_saved == 1
            worker_b = pool.submit(run, second, load_b)
            pid = b_pid.result(timeout=5)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                waiting, = conn.execute("""
                    SELECT EXISTS (
                        SELECT FROM pg_locks
                        WHERE pid = %s AND relation = 'raw.accounts'::regclass
                          AND mode = 'ShareRowExclusiveLock' AND NOT granted
                          AND pg_backend_pid() = ANY(pg_blocking_pids(pid))
                    )
                """, (pid,)).fetchone()
                if waiting:
                    return  # Let the real runtime mark SUCCESS and commit A.
                if worker_b.done():
                    worker_b.result()  # Propagate an unexpected worker error.
                    raise AssertionError("B completed before A committed")
            raise AssertionError("B never waited for A's raw.accounts lock")

        worker_b = None
        run(first, load_a)
        worker_b.result(timeout=15)

    with create_connection() as conn:
        assert conn.execute("""
            SELECT source_account_version_id, ingestion_run_id FROM raw.accounts
        """).fetchall() == [(one_account_version, first)]
        audit = conn.execute("""
            SELECT ingestion_run_id, run_status, rows_read, rows_saved, rows_skipped
            FROM ops.ingestion_runs WHERE pipeline_name = 'test_accounts_concurrent'
        """).fetchall()
        assert set(audit) == {
            (first, "SUCCESS", 1, 1, 0),
            (second, "SUCCESS", 1, 0, 1),
        }
