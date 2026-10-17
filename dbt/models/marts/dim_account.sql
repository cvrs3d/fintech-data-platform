{{ config(materialized='table')}}

with account_versions as (
    select account_version_id as account_key,
    source_account_version_id,
    account_id,
    customer_id,
    currency_id,
    registered_at_dt,
    source_effective_from_dt as valid_from,
    lead(source_effective_from_dt) over (
    partition by account_id
    order by source_effective_from_dt, source_account_version_id
    ) as valid_to,
    ingestion_run_id,
    updated_at_dt as source_updated_at_dt
    from {{ source('raw', 'accounts') }}
    where source_account_version_id is not null
)
select 
    account_key,
    source_account_version_id,
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