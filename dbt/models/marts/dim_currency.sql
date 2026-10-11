{{ config(materialized='table') }}

select
    currency_id as currency_key,
    currency_id,
    currency_code,
    registered_at_dt,
    ingestion_run_id,
    updated_at_dt as source_updated_at_dt
from {{ source('raw', 'currency') }}