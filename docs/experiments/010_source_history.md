# Source history for customers and accounts

## Purpose

The original loaders compared the current source row with the latest RAW row.
A change followed by a reversal between batch runs could be missed completely.
The original dimensions also used `inserted_at_dt`, which describes when the
platform observed a version.

Source history now records each insert and each tracked attribute change.
Loaders consume these version records, and dimensions use their effective
timestamps. This prepares the data for selecting dimension versions at an
entry's `executed_at_dt`; the fact model and temporal joins are a later step.

## Source capture

| Entity | History table | Source version identifier | Tracked update fields |
|---|---|---|---|
| Customer | `source.customer_history` | `source_customer_version_id` | `first_name`, `last_name`, `birth_date`, `death_date`, `registered_at_dt` |
| Account | `source.account_history` | `source_account_version_id` | `currency_id`, `customer_id`, `registered_at_dt` |

An `AFTER INSERT` trigger captures the initial version of a new entity.
An `AFTER UPDATE` trigger uses `IS DISTINCT FROM` on the tracked fields, including
nullable values. Updating only technical timestamps does not create a version.

Each history row contains a snapshot of the attributes, the original
`created_at_dt` and `updated_at_dt`, and two timestamps:

- `effective_from_dt`: assigned with `clock_timestamp()` when the trigger runs.
- `recorded_at_dt`: assigned when the history row is written.

Both timestamps belong to the source history. They are separate from RAW
ingestion time. The current source contract assumes that tracked changes take
effect immediately; it does not accept backdated effective times.

The trigger insert participates in the source transaction. Rolling back the
transaction also removes its history rows. Version identifiers may have gaps;
they identify versions and do not need to match customer or account IDs.

## Migrations and compatibility

| Migration | Change |
|---|---|
| `010_source_account_history.sql` | Account history, triggers and initial snapshot |
| `011_raw_accounts_source_history.sql` | Source version identifier and effective timestamp in RAW accounts |
| `012_source_customer_history.sql` | Customer history, triggers and initial snapshot |
| `013_raw_customers_source_history.sql` | Source version identifier and effective timestamp in RAW customers |

Each history migration takes an initial snapshot of existing source rows.
Its effective timestamp is the snapshot time, not the entity's creation date.
These snapshots do not reconstruct earlier history.

Existing RAW rows remain in place. Their newly added source history fields are
NULL, so both dimensions exclude them using
`WHERE source_*_version_id IS NOT NULL`. This avoids mixing observation time
with source effective time.

For an existing database, apply only migrations that have not already run.
The README bootstrap loop is for a fresh database.

## RAW ingestion

The loaders read the full history table in source version identifier order.
For each row they:

1. Check whether the source version identifier already exists in RAW.
2. Skip an existing version and increment `rows_skipped`.
3. Insert an unseen version with its snapshot, `source_effective_from_dt` and
   `ingestion_run_id`, then increment `rows_saved`.

A return to earlier attribute values is still a new version because its source
version identifier is different. A UNIQUE constraint protects each source
version identifier in RAW.

Account ingestion retains its owner-change validation: a new version with a
different `customer_id` from the latest stored account version fails the run.
This validation is separate from the source trigger's ability to record changes.

The loader commits a RUNNING record before data processing. RAW inserts and the
SUCCESS status are committed together. On failure, RAW changes are rolled back,
then FAILED is recorded with `rows_saved = 0`, and the exception is raised.

## Dimensions

Both dimensions are rebuilt as dbt tables, with one row per loaded source
history version.

| Output field | Customer dimension | Account dimension |
|---|---|---|
| Dimension key | `customer_version_id AS customer_key` | `account_version_id AS account_key` |
| Source version identifier | `source_customer_version_id` | `source_account_version_id` |
| Business identifier | `customer_id` | `account_id` |
| `valid_from` | `source_effective_from_dt` | `source_effective_from_dt` |

`valid_to` is the next effective timestamp for the same business identifier,
calculated with `LEAD`. Ordering uses the effective timestamp followed by the
source version identifier. Intervals are half-open: `[valid_from, valid_to)`.
The final version has `valid_to IS NULL` and `is_current = true`.

Dimension keys are retained across builds while the underlying RAW rows are
retained. dbt tests check key uniqueness, required values, exactly one current
version per entity, and valid intervals.

## Manual validation on 2026-10-17

### Customer trigger rollback

Within one transaction, customer 1 changed from `death_date = NULL` to a date
and back to NULL. Both changes appeared in source history. After ROLLBACK,
only that customer's baseline version remained.

### Initial customer ingestion

The observed run records were:

| Run | Status | Rows read | Rows saved | Rows skipped |
|---|---|---:|---:|---:|
| Initial load | SUCCESS | 2 | 2 | 0 |
| Repeat | SUCCESS | 2 | 0 | 2 |

The initial `dim_customer` build produced two rows and passed all nine data tests.

### Two committed changes between loads

Customer 1 changed from `Doe` to `Doe_test` and back to `Doe`.
Each update was committed separately. Ingestion ran only after both changes.

The resulting dimension contained:

| Customer ID | Source version ID | Last name | Valid from (UTC) | Valid to (UTC) | Current |
|---|---|---|---|---|---|
| 1 | 2 | Doe | 2026-10-17 18:21:17.382499 | 2026-10-17 19:07:43.790717 | false |
| 1 | 5 | Doe_test | 2026-10-17 19:07:43.790717 | 2026-10-17 19:07:43.792462 | false |
| 1 | 6 | Doe | 2026-10-17 19:07:43.792462 | NULL | true |
| 2 | 1 | Doe | 2026-10-17 18:21:17.382322 | NULL | true |

The intermediate version survived even though the current source surname was
already back to its original value when ingestion ran.

An earlier account experiment also preserved both committed registration-date
changes: `2026-10-02 → 2026-10-03 → 2026-10-02`. Account 1 had three versions;
account 2 retained one version.

## CI contract

CI initializes a fresh database, applies migrations through 013, runs each
customer and account loader twice, builds the four dbt models, and runs
`tests/check_pipeline.py`.

The clean database is expected to contain two rows in each customer and account
source, source history, RAW and dimension table. Entries have two rows in each
layer, and currency has one row in each layer.

For each of `source_customers_to_raw` and `source_accounts_to_raw`, the run-log
check expects the following records in chronological order:

| Run | Status | Rows read | Rows saved | Rows skipped |
|---|---|---:|---:|---:|
| Initial load | SUCCESS | 2 | 2 | 0 |
| Repeat | SUCCESS | 2 | 0 | 2 |

These assertions validate both the stored data and ingestion counters.
They describe the CI acceptance criteria, not a recorded CI result for this
change. A development database with additional versions or run records will not
match these clean-database expectations.

## Current limits

- Ingestion uses a full scan with `fetchall()` and a single ingestion worker.
- Source history is treated as append-only; corrections to existing history
  records are not propagated by version-ID deduplication.
- Deletes and backdated changes are not captured by this implementation.
- Trigger timestamps describe when triggers ran, not transaction commit order.
  Concurrent source changes and transfers need an explicit ordering contract
  before exact temporal matching can be guaranteed.
- Events before an entity's initial snapshot have no authoritative version in
  this history. A future fact model must make this lack of coverage explicit.
