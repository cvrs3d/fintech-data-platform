# Account ingestion: profiling, regression and COMMIT recovery

Baseline: `d74fed22054a71f7cb4f86b6d102ff5c47c06280`. Measured code: `461bb717a4effa8ba6b7e36d093128066b47dd2e`.
Local Linux x86_64, PostgreSQL 16.2, Python 3.13.5, psycopg 3.3.6. This is a controlled comparison on one host, not a latency forecast for the ARM VM.

## Reproduce (manual only)

Use an **exclusive disposable local database named fintech_test**. The benchmark truncates source.account_history, raw.accounts and ops.ingestion_runs, resets their identities, and leaves the last replay available for inspection. Never share this database with pytest, Airflow or another benchmark. Use a local PG instance or local container capped at 1 GiB. The measured instance used shared_buffers=32MB, work_mem=4MB, max_connections=8, max_parallel_workers=0; one worker at a time. No Airflow or dbt services.

From the repository root, with the project's PostgreSQL credentials in the environment (or .env) and a local host address:

```bash
# Only if fintech_test does not already exist:
docker compose exec -T postgres createdb -U postgres fintech_test
# On the fresh database:
for f in infra/sql/{001_source_schema,005_raw_entries,006_ingestion_runs,008_raw_accounts,009_raw_currency,010_source_account_history,011_raw_accounts_source_history}.sql; do
  docker compose exec -T postgres psql -X -v ON_ERROR_STOP=1 -1 -U postgres -d fintech_test -f - < "$f" || exit 1
done

export POSTGRES_DB=fintech_test POSTGRES_HOST=127.0.0.1 PYTHONPATH=ingestion:.
uv run --locked --env-file .env python -m pytest -q tests/
# BASE must be present in git history (fetch it if using a shallow clone).
timeout 600 uv run --locked --env-file .env python benchmarks/profile_accounts.py
```

Seed 1729 rotates account IDs; each account has four interleaved versions, fixed timestamps and one owner. Both implementations get the same IDs and fields. The harness reads the original loader from the pinned commit, resets and analyzes tables before each first/replay pair, and runs each phase in a fresh Python process. Time covers connection, load, audit commits and close. RSS is Linux peak process RSS through return from the loader, including native buffers and imports. Counts come from a separate identical run: libpq frontend Query/Execute, including transaction control, audit, DECLARE/FETCH/CLOSE, excluding seed and verification. No trace overhead in the timing column. Every phase checks committed audit, version count, ownership and effective times over a new connection. Single timing sample per cell; no cache eviction, remote latency, competing jobs or timing gate in PR CI.

## Measurements and plans

| versions | impl | phase | seconds | RSS MiB | SQL | read/saved/skipped |
|---:|---|---|---:|---:|---:|---|
| 100 | base | first | 0.0196 | 30.3 | 307 | 100/100/0 |
| 100 | base | replay | 0.0098 | 30.3 | 107 | 100/0/100 |
| 100 | batch | first | 0.0170 | 30.4 | 112 | 100/100/0 |
| 100 | batch | replay | 0.0073 | 30.2 | 11 | 100/0/100 |
| 1000 | base | first | 0.2696 | 30.8 | 3007 | 1000/1000/0 |
| 1000 | base | replay | 0.0388 | 30.8 | 1007 | 1000/0/1000 |
| 1000 | batch | first | 0.0589 | 30.7 | 1018 | 1000/1000/0 |
| 1000 | batch | replay | 0.0091 | 30.6 | 14 | 1000/0/1000 |
| 10000 | base | first | 7.6568 | 36.2 | 30007 | 10000/10000/0 |
| 10000 | base | replay | 0.4697 | 36.1 | 10007 | 10000/0/10000 |
| 10000 | batch | first | 0.7545 | 31.9 | 10090 | 10000/10000/0 |
| 10000 | batch | replay | 0.0393 | 30.6 | 50 | 10000/0/10000 |

Version lookup
```text
WindowAgg  (cost=0.57..1068.57 rows=10000 width=57) (actual time=6.092..7.041 rows=10000 loops=1)
  Buffers: shared hit=305
  ->  Merge Left Join  (cost=0.57..943.57 rows=10000 width=56) (actual time=0.017..4.036 rows=10000 loops=1)
        Merge Cond: (h.source_account_version_id = r.source_account_version_id)
        Buffers: shared hit=305
        ->  Index Scan using account_history_pkey on account_history h  (cost=0.29..377.29 rows=10000 width=48) (actual time=0.003..0.885 rows=10000 loops=1)
              Buffers: shared hit=133
        ->  Index Only Scan using accounts_source_account_version_id_key on accounts r  (cost=0.29..416.29 rows=10000 width=8) (actual time=0.005..1.318 rows=10000 loops=1)
              Heap Fetches: 10000
              Buffers: shared hit=172
Planning:
  Buffers: shared hit=91
Planning Time: 0.230 ms
Execution Time: 7.350 ms
```

Latest owners
```text
Unique  (cost=280.72..280.78 rows=12 width=16) (actual time=0.947..0.950 rows=3 loops=1)
  Buffers: shared hit=143
  ->  Sort  (cost=280.72..280.75 rows=12 width=16) (actual time=0.946..0.947 rows=12 loops=1)
        Sort Key: account_id, account_version_id DESC
        Sort Method: quicksort  Memory: 25kB
        Buffers: shared hit=143
        ->  Seq Scan on accounts  (cost=0.00..280.50 rows=12 width=16) (actual time=0.043..0.939 rows=12 loops=1)
              Filter: (account_id = ANY ('{1,2,3}'::smallint[]))
              Rows Removed by Filter: 9988
              Buffers: shared hit=143
Planning:
  Buffers: shared hit=58
Planning Time: 0.085 ms
Execution Time: 0.958 ms
```
PostgreSQL: 160002 | seed: 1729
Elapsed (including setup, validation, traces): 23.21s

PostgreSQL sampled aggregate RSS: 45.7 MiB (sum of all local postgres process RSS every 50 ms, shared pages may be counted twice; this sampled maximum is not a hard limit).

## Why change the read path?

The baseline transfers the entire source to Python, probes RAW for every version, and queries the last owner for every insert. A server-side cursor now reads a single source/RAW join in pages of 256. The window count preserves the meaning of rows_read even when a business error interrupts the batch. Per nonempty page of new versions we fetch the latest RAW owner of each account once, including legacy RAW rows. We update the page's owner map immediately: the second version of a new account cannot silently change its owner. A later page reads prior uncommitted inserts on the same connection. Replayed version IDs are skipped before ownership validation, as before. There is still one INSERT per accepted version and one commit for all RAW changes and SUCCESS.

At 10,000 versions this removes 66.4% of first-load statements and 99.5% on replay. Python holds a page and its owner map; PostgreSQL still reads the entire history and may spool/sort it. The owner query can scan RAW once per page without an account index; the plan above is not evidence for unlimited scale. A future account index should be assessed against its write cost. Under the default READ COMMITTED isolation we take a SHARE ROW EXCLUSIVE lock on raw.accounts **before** opening the cursor. Competing loaders serialize until commit/rollback; ordinary readers can continue. A waiting loader pays lock latency. Unique source version IDs guard against duplicate keys, but cannot by themselves enforce one owner across different versions. Direct writers that ignore the ownership rule can still introduce invalid data.

Integration checks on two consecutive runs: **10 passed**, including pre-existing replay/quarantine tests. F1 counts three real uncommitted inserts, raises before commit, then reads FAILED / saved=0 and zero run-owned RAW rows from another connection. F2 covers a conflict against committed RAW, two different owners in one page, and a conflict across pages of size one. Empty input succeeds with 0/0/0. CI discovers regression tests under tests/; the destructive benchmark lives outside that directory and has no CI trigger.

## Incident: Airflow lost the connection during COMMIT

Pause automatic retries and overlapping writers. Take the account loader's printed ingestion_run_id from the **specific Airflow task attempt**. Each retry creates a new UUID. Check the authoritative writable primary; a lagging replica or a single observation while the original backend is still committing is inconclusive. Verify the original task has stopped and cannot start another transaction. Use a fresh READ COMMITTED session and a short lock timeout; if this times out, wait/investigate instead of drawing a conclusion.

```sql
-- In psql: set rid to the UUID from the affected attempt.
BEGIN ISOLATION LEVEL READ COMMITTED;
SET LOCAL lock_timeout = '3s';
LOCK TABLE raw.accounts IN SHARE MODE;
SELECT ingestion_run_id, run_status, rows_read, rows_saved, rows_skipped,
       start_time_dt, end_time_dt, error_cause
FROM ops.ingestion_runs WHERE ingestion_run_id = :'rid'::uuid;
SELECT count(*) AS saved, count(DISTINCT source_account_version_id) AS versions
FROM raw.accounts WHERE ingestion_run_id = :'rid'::uuid;
SELECT source_account_version_id, account_id, customer_id
FROM raw.accounts WHERE ingestion_run_id = :'rid'::uuid
ORDER BY source_account_version_id LIMIT 20;
COMMIT;
```

| Outcome of RAW + SUCCESS transaction | Evidence and action |
|---|---|
| Definitely not committed | Confirmed rollback, or FAILED + zero run-owned rows on the reconciled primary. Resolve the cause. For owner conflict inspect source history; retrying unchanged invalid history will fail again. Retry transient failures as a new attempt. |
| Confirmed committed | SUCCESS and persisted count equals rows_saved, distinct version count agrees, rows_read = rows_saved + rows_skipped. Zero RAW with SUCCESS can be legitimate on replay. Do not rerun solely because the acknowledgement was lost. |
| Unknown | Lost ACK alone proves neither outcome. RUNNING means only the initial audit commit was seen. Missing audit can mean failure before that commit. While primary/backend state is uncertain keep retries paused. After the original backend ends and the primary is stable, RUNNING + zero RAW + no SUCCESS indicates the atomic load did not persist there. Preserve the stale audit, document reconciliation, then replay. Inconsistent evidence (e.g. FAILED with RAW) or unresolved failover requires escalation; do not repair/delete rows or mark SUCCESS by hand. |

After an authorized replay, compare both run IDs and expected source version IDs. Replay scans *current* source history and may include new versions, so zero new rows is only expected on unchanged input. The runtime does not guarantee an audit write while the database is unreachable, exactly-once Airflow execution, a durable source manifest, or recovery of transactions lost during asynchronous failover. Airflow task logs provide external evidence; no DSN/password or row payload is needed.
