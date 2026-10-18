{{ config(materialized='table') }}

select
    e.entry_id,
    e.transaction_id,
    e.account_id,
    a.account_key,
    a.customer_id,
    c.customer_key,
    a.currency_id,
    cur.currency_key,
    e.amount,
    e.created_at_dt,
    e.executed_at_dt,
    e.inserted_at_dt,
    e.ingestion_run_id
from {{ ref('stg_entries') }} as e
left join {{ ref('dim_account') }} as a
    on e.account_id = a.account_id
    and e.executed_at_dt >= a.valid_from
    and (
        e.executed_at_dt < a.valid_to
        or a.valid_to is null
    )
left join {{ ref('dim_customer') }} as c
    on a.customer_id = c.customer_id
    and e.executed_at_dt >= c.valid_from
    and (
        e.executed_at_dt < c.valid_to
        or c.valid_to is null
    )
left join {{ ref('dim_currency') }} as cur
    on a.currency_id = cur.currency_id