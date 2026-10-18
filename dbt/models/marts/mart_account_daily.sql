{{ config(materialized='table') }}

select
    (executed_at_dt at time zone 'UTC')::date as activity_date,
    account_id,
    currency_key,
    count(*) as entries_count,

    case
        when currency_key is null then null
        else sum(case when amount > 0 then amount else 0 end)
    end as incoming_amount,

    case
        when currency_key is null then null
        else sum(case when amount < 0 then -amount else 0 end)
    end as outgoing_amount,

    case
        when currency_key is null then null
        else sum(amount)
    end as net_amount

from {{ ref('fact_entries') }}
group by
    activity_date,
    account_id,
    currency_key