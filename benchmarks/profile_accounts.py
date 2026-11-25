"""Manual Linux benchmark. Run from repo root on an exclusive local fintech_test."""
import json
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time
import uuid
from importlib.util import module_from_spec, spec_from_file_location

from infra import create_connection, utc_now
from runtime import run_pipeline
import load_accounts as optimized

BASE = "d74fed22054a71f7cb4f86b6d102ff5c47c06280"
SEED = 1729


def checked():
    c = create_connection()
    if (c.info.dbname != "fintech_test" or
            c.info.host not in ("localhost", "127.0.0.1", "::1")):
        c.close()
        raise RuntimeError("Requires a dedicated local fintech_test database")
    return c


def reset(n):
    with checked() as c:
        c.execute("""
            TRUNCATE source.account_history, raw.accounts, ops.ingestion_runs
            RESTART IDENTITY
        """)
        # Four versions/account; seeded permutation of the account sequence.
        c.execute("""
            INSERT INTO source.account_history
                (account_id, currency_id, customer_id, registered_at_dt, created_at_dt,
                 updated_at_dt, effective_from_dt, recorded_at_dt)
            SELECT a, 1, a, DATE '2020-01-01', t, t, t, t
            FROM (SELECT i, 1 + mod(i + %s, %s) AS a,
                         timestamptz '2020-01-01 00:00+00' + i * interval '1 second' AS t
                  FROM generate_series(0, %s - 1) i) s ORDER BY i
        """, (SEED, n // 4, n))
        c.execute("ANALYZE source.account_history")
        c.execute("ANALYZE raw.accounts")


def worker(module_path, n, replay, traced):
    spec = spec_from_file_location("measured_accounts", module_path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    run_id = uuid.uuid4()
    with tempfile.TemporaryFile() as wire:
        def connect():
            # checked() has guarded setup; info checks send no SQL.
            c = checked()
            if traced:
                c.pgconn.trace(wire.fileno())
            return c

        start = time.perf_counter()
        run_pipeline("profile_accounts", connect, utc_now, lambda: run_id, module.account_ingestion)
        seconds = time.perf_counter() - start
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        wire.seek(0)
        statements = sum(1 for line in wire if line.split(b'\t', 4)[1:4:2]
                         in ([b'F', b'Query'], [b'F', b'Execute']))
    with checked() as c:
        audit = c.execute("""
            SELECT run_status, rows_read, rows_saved, rows_skipped, error_cause
            FROM ops.ingestion_runs WHERE ingestion_run_id = %s
        """, (run_id,)).fetchone()
        saved = 0 if replay else n
        assert audit == ("SUCCESS", n, saved, n - saved, None), audit
        assert c.execute("""
            SELECT count(*), count(*) FILTER (WHERE ingestion_run_id = %s),
                   count(DISTINCT source_account_version_id) FROM raw.accounts
        """, (run_id,)).fetchone() == (n, saved, n)
        assert not c.execute("""
            SELECT 1 FROM source.account_history h
            LEFT JOIN raw.accounts r USING (source_account_version_id)
            WHERE (h.account_id,h.customer_id,h.currency_id,h.effective_from_dt)
              IS DISTINCT FROM (r.account_id,r.customer_id,r.currency_id,r.source_effective_from_dt)
            LIMIT 1
        """).fetchone()
    print(json.dumps([seconds, rss, statements, audit[1:4]]))


def main():
    start = time.monotonic()
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "baseline.py"
        base.write_bytes(subprocess.check_output(["git", "show", BASE + ":ingestion/load_accounts.py"]))
        print("| versions | impl | phase | seconds | RSS MiB | SQL | read/saved/skipped |", flush=True)
        print("|---:|---|---|---:|---:|---:|---|")
        for n in (100, 1000, 10000):
            for label, path in (("base", base), ("batch", Path(optimized.__file__))):
                results = []
                for traced in (0, 1):
                    reset(n)
                    for replay in (0, 1):
                        args = [sys.executable, __file__, str(path), str(n), str(replay), str(traced)]
                        remaining = 600 - (time.monotonic() - start)
                        results.append(json.loads(subprocess.check_output(args, timeout=max(0.1, remaining))))
                for i, phase in enumerate(("first", "replay")):
                    sec, rss, _, audit = results[i]
                    print(f"| {n} | {label} | {phase} | {sec:.4f} | {rss:.1f} | "
                          f"{results[i+2][2]} | {'/'.join(map(str, audit))} |", flush=True)
        with checked() as c:
            c.execute("ANALYZE raw.accounts")
            for title, sql, params in (("Version lookup", optimized.VERSIONS, ()),
                                       ("Latest owners", optimized.OWNERS, ([1, 2, 3],))):
                print(f"\n{title}\n```text")
                for line, in c.execute("EXPLAIN (ANALYZE, BUFFERS) " + sql, params):
                    print(line)
                print("```")
            print("PostgreSQL:", c.info.server_version, "| seed:", SEED)
        print(f"Elapsed (including setup, validation, traces): {time.monotonic()-start:.2f}s")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        main()
    else:
        worker(sys.argv[1], *map(int, sys.argv[2:]))
