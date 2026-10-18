# Daily account activity mart

## Purpose and grain

`mart_account_daily` summarizes executed account entries from `fact_entries`.
Its grain is one row per UTC activity date, business `account_id` and
`currency_key`, including a separate unresolved-currency group when needed.

The model is defined in `dbt/models/marts/mart_account_daily.sql` and materialized
as a table. With the current profile, its database name is
`staging.mart_account_daily`.

Grouping by `account_id` combines versions of the same account within a day
when their currency key is the same. Different known currencies remain separate.
Days without entries do not produce rows. The metrics describe daily movement;
they do not provide opening or closing account balances.

## Metrics

| Column | Definition |
|---|---|
| `activity_date` | `(executed_at_dt at time zone 'UTC')::date` |
| `account_id` | Business account identifier from the fact |
| `currency_key` | Resolved currency key, or NULL when unresolved |
| `entries_count` | Number of fact entries in the group |
| `incoming_amount` | Sum of positive amounts; zero if none, for a known currency |
| `outgoing_amount` | Sum of negated negative amounts; zero if none, for a known currency |
| `net_amount` | Signed sum of amounts, for a known currency |

Incoming and outgoing amounts are nonnegative. For a known currency:

```text
net_amount = incoming_amount - outgoing_amount
```

The explicit UTC conversion makes the date independent of the database
session's time zone. `entries_count` counts entries, not distinct transfers:
a transfer creates one entry for each participating account.

## Unresolved currency

An entry may lack a currency key because its execution predates known account
history. The fact preserves that entry; the mart also preserves it in the
appropriate date/account group with `currency_key IS NULL`.

For such groups, `entries_count` is populated, but `incoming_amount`,
`outgoing_amount` and `net_amount` are all NULL. A NULL currency does not identify
a shared monetary unit, so amounts in that group are not reported as a total.
NULL totals must not be replaced with zero or assigned a current currency.

The mart performs no currency conversion. Monetary totals across different
known currencies also require an explicit conversion rule before aggregation.

Both the fact and mart are rebuilt as tables. If a later build resolves missing
history, an entry can move from an unresolved group to a known currency group.
The earlier history is not inferred or backdated by this model.

See [Fact entries and temporal dimension joins](011_fact_entries.md) for the
upstream lookup rules.

## Data-quality checks

`dbt/models/marts/_models.yml` declares not-null tests for `activity_date`,
`account_id` and `entries_count`. The currency key and monetary metrics are
intentionally nullable under the rule above.

Three singular tests return rows only when an invariant is violated:

| Test | Checked invariant |
|---|---|
| `assert_mart_account_daily_grain` | At most one row per date/account/currency group, including NULL currency |
| `assert_mart_account_daily_metrics` | Positive entry count; NULL totals for unresolved currency; populated totals, nonnegative incoming/outgoing amounts and consistent net movement for known currency |
| `assert_mart_account_daily_preserve_count` | Sum of mart entry counts equals the fact row count |

The count reconciliation uses `coalesce(sum(entries_count), 0)` so that two empty
tables reconcile to zero. These checks validate the stated invariants; they do
not independently recalculate every group's monetary totals from the fact.

## Validation on the development VM

The build on 2026-10-18 produced 16 fact rows and 10 daily mart rows:

- Fourteen entries executed on October 2-5 remained in eight unresolved-currency
  groups. Their counts were retained and all three monetary totals were NULL.
- Two entries executed on October 18 resolved to currency key 1 and produced
  the following rows.

| Activity date | Account ID | Currency key | Entries | Incoming | Outgoing | Net |
|---|---:|---:|---:|---:|---:|---:|
| 2026-10-18 | 1 | 1 | 1 | 0.00 | 10.00 | -10.00 |
| 2026-10-18 | 2 | 1 | 1 | 10.00 | 0.00 | 10.00 |

The six models, 47 data tests and one upstream fact unit test completed
successfully: `PASS=54, WARN=0, ERROR=0, SKIP=0`. The sum of `entries_count`
across the 10 mart rows was 16.

## Build and CI expectations

After running the RAW loaders, execute from the project root:

```bash
uv run --locked --env-file .env dbt build \
  --project-dir dbt \
  --profiles-dir dbt \
  --select +mart_account_daily
```

The leading `+` includes the upstream fact, dimensions and staging model.
CI uses this selection with credentials supplied through environment variables,
without `--env-file .env`.

The clean CI fixture contains two entries, one for each of two accounts on the
same UTC date. They precede the history snapshots, so the expected mart has two
rows with NULL currency keys and monetary totals, and one entry per row.

`tests/check_pipeline.py` includes `staging.mart_account_daily` as its final
table count, with an expected value of 2. Its fixed counts and ingestion-run
assertions apply to the fresh CI database; the development VM has additional
history and entries. The observed VM build above is separate from the result
of the GitHub Actions run for this change.
