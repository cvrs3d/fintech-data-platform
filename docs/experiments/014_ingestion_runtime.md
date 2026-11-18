# Shared ingestion runtime and failure handling

VM validation: 2026-11-17 and 2026-11-18.

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

## Isolated pytest suite (2026-11-18)

The runtime tests use a dedicated PostgreSQL database, `fintech_test`.
On a fresh database, apply migrations 001, 005, 006, 008, 009, 010 and 011
from `infra/sql/` in order, one file at a time. Skip demo data and baseline
ingestion: pytest fixtures prepare the data for each scenario.

Run from the repository root:

    PYTHONPATH=ingestion uv run --locked python -m pytest -q tests/

An autouse fixture sets `POSTGRES_DB=fintech_test` so that connections opened
by the runtime also use the test database. Before truncating tables, setup
checks `current_database()` on the connection that will perform the cleanup.
Run the tests sequentially because they reset shared test tables.

| Scenario | Expected persisted state |
| --- | --- |
| Account first load and replay | The fixture creates one source history version and leaves RAW empty. The first run saves it; the second skips it. RAW still contains one version. |
| Failure after RAW insertion | The inserted row rolls back. A new connection sees a FAILED audit with zero saved and the original error. |
| Connection failure | The factory raises before RUNNING. The caller receives the error and no audit row exists for the run UUID. |
| Currency conflict | The fixture seeds matching source and RAW codes. A conflicting source change rolls back; quarantine and FAILED record the conflict. |
| Quarantine failure | A deliberate SQL error after the quarantine insert rolls that insert back to the savepoint. FAILED retains the original currency conflict. |

Observed on the VM: `first_saved=1, second_saved=0, second_skipped=1`
for the isolated account test (`1 passed in 0.19s`). Both currency tests
also passed individually.

CI keeps the existing pipeline count checks on `fintech` and initializes
`fintech_test` separately for pytest. The expected suite result is `5 passed`.

## Historical resource measurement (2026-11-17)

These figures were measured before the switch to pytest. Each module ran as
a separate Python process against the populated development database.

| Module | Peak Python RSS (KiB) | Elapsed (s) |
| --- | ---: | ---: |
| `tests.test_ingestion_runtime` | 43200 | 0.24 |
| `tests.test_connection_runtime` | 42844 | 0.22 |
| `tests.test_currency_quarantine` | 41204 | 0.28 |
| `tests.test_currency_quarantine_failure` | 43268 | 0.30 |
| `tests.test_accounts_repeat` | 42980 | 0.31 |

Peak RSS was 43268 KiB (42.25 MiB), below the 512 MiB test-process budget.
This excludes PostgreSQL and is not a measurement of the current pytest suite.
The original repeat test skipped four existing versions; the isolated test
also verifies the first insertion.

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
