select
    coalesce(sum(entries_count), 0) as mart_entries_count
from {{ ref('mart_account_daily') }}
having coalesce(sum(entries_count), 0) <> (
    select count(*)
    from {{ ref('fact_entries') }}
)