{{ config(materialized='table')}}
with customer_versions as (
    select 
        customer_version_id AS customer_key, 
        source_customer_version_id,
        customer_id, 
        source_effective_from_dt AS valid_from,
        lead(source_effective_from_dt) OVER (
            PARTITION BY customer_id
            ORDER BY source_effective_from_dt, source_customer_version_id
        ) AS valid_to, 
        first_name, 
        last_name, 
        birth_date, 
        death_date, 
        registered_at_dt, 
        ingestion_run_id,
        updated_at_dt AS source_updated_at_dt,
        source_effective_from_dt
    FROM {{ source('raw', 'customers') }}
    WHERE source_customer_version_id IS NOT NULL
)
select
    customer_key,
    source_customer_version_id,
    customer_id,
    valid_from,
    valid_to,
    first_name,
    last_name,
    birth_date,
    death_date,
    registered_at_dt,
    ingestion_run_id,
    source_updated_at_dt,
    source_effective_from_dt,
    valid_to is null as is_current
from customer_versions