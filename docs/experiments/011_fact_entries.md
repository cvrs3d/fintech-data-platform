# Fact entries and temporal dimension joins

## Purpose and grain

`fact_entries` enriches `stg_entries` with account, customer and currency keys.
Its grain is one row per `entry_id`. A transfer contains two entries sharing a
`transaction_id`, so `transaction_id` is not unique in the fact.

The model is defined in `dbt/models/marts/fact_entries.sql` and materialized as a
table. With the current profile it is built as `staging.fact_entries`.

## Mapping

| Output | Source |
|---|---|
| `entry_id`, `transaction_id`, `account_id`, `amount` | Unchanged from `stg_entries` |
| `created_at_dt`, `executed_at_dt`, `inserted_at_dt`, `ingestion_run_id` | Unchanged from `stg_entries` |
| `account_key` | Matched version in `dim_account` |
| `customer_id`, `currency_id` | Matched account version |
| `customer_key` | Matched version in `dim_customer` |
| `currency_key` | Matching reference row in `dim_currency` |

`ingestion_run_id` identifies the entry's RAW ingestion run; it is not a dbt
build identifier.

## Version selection

Account lookup matches the entry's `account_id` and the account interval
containing `executed_at_dt`:

```sql
e.account_id = a.account_id
and e.executed_at_dt >= a.valid_from
and (
    e.executed_at_dt < a.valid_to
    or a.valid_to is null
)
```

Customer lookup uses `customer_id` from that account version and the same
entry execution timestamp. It does not use the account version's start time:
customer attributes can change while an account version remains unchanged.

Both lookups use half-open intervals, `[valid_from, valid_to)`. A timestamp
equal to the next version's start belongs to the next version. There is no
`is_current` filter.

Currency lookup matches the account version's `currency_id` to
`dim_currency.currency_id`. The currency reference is not versioned; the loader
rejects a changed code for an existing currency identifier.

All three joins are LEFT JOINs. The temporal conditions remain in their ON
clauses so that unmatched entries are preserved.

## Missing history

Source history starts at the initial snapshot. It cannot establish the state
of an entity before that snapshot.

If no account version matches an entry, the fact retains its original fields,
including `account_id` and `amount`. The account key and all derived customer
and currency fields are NULL.

If an account version exists but a customer version is unavailable, the known
`customer_id` is retained and `customer_key` is NULL. These NULL keys represent
unresolved lookups; they are not replaced with current or earliest versions.

Consumers must retain unresolved entries when reporting overall entry counts.
Currency-specific or customer-specific reporting should expose the unresolved
portion separately. A NULL currency must not be interpreted as a known currency.

The table is rebuilt on each run. Later builds can resolve previously missing
keys if suitable historical versions become available.

See [Source history for customers and accounts](010_source_history.md) for the
effective-time contract and its concurrency limitations.

## Validation on the development VM

On 2026-10-18, the initial fact contained 14 entries executed between October 2
and October 5. Account history began on October 17, so all 14 entries were
retained with NULL account keys.

A new test transfer of 10.00 was then created between accounts 1 and 2. Both
entries were executed at `2026-10-18 11:32:20.604039+00`. After ingestion and
rebuilding the fact, the observed mappings were:

| Entry ID | Account ID | Account key | Customer ID | Customer key |
|---|---:|---:|---:|---:|
| 16 | 1 | 8 | 1 | 8 |
| 17 | 2 | 6 | 2 | 5 |

These generated keys describe this VM's data; they are not expected identifiers
for a fresh database.

The completed build produced 16 fact rows. All five models and 41 data tests
completed successfully: `PASS=46, WARN=0, ERROR=0`.

## Automated checks

The model's tests are declared in `dbt/models/marts/_models.yml`:

- `entry_id`: unique and not null.
- `transaction_id`, `account_id`, `amount`, `executed_at_dt`: not null.
- `account_key`, `customer_key`, `currency_key`: relationships to the
  corresponding dimension key.

Dimension keys intentionally have no not-null test. Relationship tests check
that non-null keys exist; they do not independently verify temporal selection.

`dbt/tests/assert_fact_entries_preserve_entries.sql` compares the entry IDs
in staging and the fact with a FULL OUTER JOIN. Missing and unexpected IDs fail
the test. Combined with uniqueness checks, this verifies one fact row per
staging entry.

## Build and CI expectations

Run from the project root after ingesting the required source data:

```bash
uv run --locked --env-file .env dbt build \
  --project-dir dbt \
  --profiles-dir dbt \
  --select +fact_entries
```

The leading `+` includes all upstream models. CI uses the same selection with
credentials supplied through environment variables, without `--env-file .env`.

The clean CI fixture contains two entries created before the history snapshots.
The expected fact count is therefore two, with unresolved dimension keys.
`tests/check_pipeline.py` adds this count to its existing table-count and
ingestion-run assertions.

These are the CI acceptance criteria for this change. The local build result
above does not establish the result of a GitHub Actions run.
