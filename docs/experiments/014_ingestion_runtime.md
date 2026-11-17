# Shared ingestion runtime and failure handling

Validated on the development VM on 2026-11-17.

## Scope

Accounts and currency now use a shared runtime for connection ownership,
run metadata, audit updates, and transaction boundaries. Entity SQL and
business rules remain in their pipeline modules.

Customers and entries retain their existing lifecycle implementation for now.
All four loaders use the connection creation mechanism in `ingestion/infra.py`;
the `with_connection` decorator remains available for the two older loaders.
Completing their lifecycle migration is a follow-up, not a claim of this change.

## Responsibilities

- `create_connection`: reads environment settings and returns an open Psycopg
  connection with autocommit disabled.
- `run_pipeline`: owns the connection, run UUID, audit lifecycle, transaction
  boundaries, and final connection closure.
- `RunContext` and `RunStats`: expose the run UUID and mutable processing counters
  to the pipeline, including when the pipeline exits with an exception.
- Pipeline functions: read source data, apply existing business checks, write RAW,
  and update counters. They do not commit, roll back, or close the connection.
- Optional `on_failure`: performs entity-specific recovery writes. Currency uses
  this callback to write quarantine records from `CurrencyCodeChanged` attributes.

The connection factory, clock, UUID generator, pipeline, and failure handler are
passed as functions. Repository responsibilities remain in entity-specific SQL
functions; no generic repository framework was introduced.

## Transaction contract

| Boundary | Operations | Outcome |
| --- | --- | --- |
| T1 | Insert `RUNNING` | Commit before invoking the pipeline |
| T2 | Pipeline SQL and `UPDATE SUCCESS` | Commit together on success |
| T2 failure | Ordinary pipeline or SQL error before commit | Roll back uncommitted changes |
| T3 | Optional failure callback and `UPDATE FAILED` | Commit separately after T2 rollback |

T3 uses an outer `connection.transaction()` block. The failure callback runs
inside a nested transaction block, which establishes a savepoint. Its exception
is caught outside the inner block and inside the outer block. A callback failure
therefore rolls back its writes while allowing `FAILED` to be persisted.

The original pipeline exception remains the audit cause and is re-raised after
failure handling. Secondary callback/audit errors are logged with pipeline name,
run UUID, and exception type. Connection credentials are not explicitly logged.
Arbitrary exception messages are not guaranteed to be free of sensitive data;
the stored original error text and propagated tracebacks need that consideration
when introducing new pipelines or exceptions.

After a confirmed rollback, the FAILED audit records `rows_saved = 0`.
`rows_read` and `rows_skipped` describe work performed before failure; they do not
have to sum to the number of source rows on an unsuccessful run.

## Preserved business behavior

- Accounts read source history and skip already loaded source version IDs.
  Changing the owner of an existing account still raises an error.
- Currency inserts new IDs and skips an existing ID with the same code.
- A changed currency code raises `CurrencyCodeChanged`, rolls back the load,
  and records the conflict in quarantine during failure handling.
- A quarantine write failure does not turn the original conflict into success
  or replace its cause with the secondary SQL exception.

## Validation on the VM

Tests ran sequentially against the existing development PostgreSQL database.
Each verification used a new connection to inspect persisted state.

| Test module | Result | Peak RSS (KiB) | Elapsed (s) |
| --- | --- | ---: | ---: |
| `tests.test_ingestion_runtime` | PASS: insert rolled back, FAILED audit and original error preserved | 43200 | 0.24 |
| `tests.test_connection_runtime` | PASS: injected connection failure, no audit row | 42844 | 0.22 |
| `tests.test_currency_quarantine` | PASS: source change rolled back, RAW unchanged, quarantine and FAILED saved | 41204 | 0.28 |
| `tests.test_currency_quarantine_failure` | PASS: quarantine insert rolled back to savepoint, original cause and FAILED saved | 43268 | 0.30 |
| `tests.test_accounts_repeat` | PASS: both runs successful, second saved 0 and skipped 4 | 42980 | 0.31 |

Maximum observed Python-process RSS was 43268 KiB, approximately 42.25 MiB,
below the 512 MiB test-process budget. PostgreSQL memory is excluded. These are
small-fixture results, not a benchmark of large source histories.

The quarantine failure test deliberately executes `SELECT 1 / 0` after a real
quarantine insert. Its `DivisionByZero` error log is expected; the original
currency conflict remains the exception seen by the caller and the audit cause.
The connection failure test injects an exception in the factory rather than
stopping the real database.

The repeat test observed `first_saved=0`, `second_saved=0`, `second_skipped=4`.
It proves repeat behavior for existing loaded history; this run did not exercise
a successful insertion of a new account version.

## Running the tests

Run from the repository root after schema initialization and baseline ingestion.
Keep source data unchanged and do not run competing loaders during these tests.
The tests leave audit records and, where expected, quarantine records behind.

```bash
(
    set -e
    for test_module in \
        tests.test_ingestion_runtime \
        tests.test_connection_runtime \
        tests.test_currency_quarantine \
        tests.test_currency_quarantine_failure \
        tests.test_accounts_repeat
    do
        PYTHONPATH=ingestion /usr/bin/time \
            -f 'Peak RAM: %M KiB | Elapsed: %e s' \
            .venv/bin/python -m "$test_module"
    done
)
```

`PYTHONPATH=ingestion` supports the existing sibling imports in the loaders.
These tests are executable modules; some assertions live under the main guard,
so pytest collection alone is not equivalent to running all five modules.
In CI, execute the modules sequentially after the existing pipeline count check.
The local results above do not substitute for the PR's clean-database CI run.

## Entry points and limitations

Existing script entry points remain `python ingestion/load_accounts.py` and
`python ingestion/load_currency.py`, preserving the Airflow commands. The image
copies ingestion code at build time, so deploying these changes requires rebuilding
the pipeline image. No new Airflow container validation is claimed here.

- If the database is unavailable, FAILED cannot be guaranteed in that database.
  Exceptions propagate to the caller, allowing Airflow task state and external
  logs to expose the failure. A previously committed RUNNING row may remain.
- A connection loss during COMMIT can leave the outcome unknown to the client.
  This implementation does not reconcile ambiguous commit outcomes; it must not
  be described as proving a rollback in that case.
- Process termination can prevent failure handling from running. There is no
  automatic reconciliation of abandoned RUNNING records in this change.
- Sequential idempotency is tested. A SELECT-before-INSERT check alone does not
  prevent concurrent races: database uniqueness constraints remain essential,
  and a competing insert can still make a run fail.
- Identity sequence increments are not rolled back with inserted rows. Gaps
  created by rollback tests are expected.
- Runtime assumes pipelines and failure callbacks obey transaction ownership:
  they must not commit, roll back, or close the shared connection themselves.
- Commit in `finally` would risk persisting partial work after a Python error.
  The finalizer closes the connection; successful commits occur only at the
  explicit lifecycle boundaries described above.
