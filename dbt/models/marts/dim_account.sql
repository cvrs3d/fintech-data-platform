{{ config(materialized='table')}}

with account_versions as (
    select account_version_id as account_key,
    account_id,
    customer_id,
    currency_id,
    registered_at_dt,
    inserted_at_dt as valid_from,
    LEAD(inserted_at_dt) OVER (
        PARTITION BY account_id
        ORDER BY account_version_id
    ) as valid_to,
    ingestion_run_id,
    updated_at_dt as source_updated_at_dt
    from {{ source('raw', 'accounts') }}
)
select 
    account_key,
    account_id,
    customer_id,
    currency_id,
    registered_at_dt,
    valid_from,
    valid_to,
    ingestion_run_id,
    source_updated_at_dt,
    valid_to is null as is_current
from account_versions