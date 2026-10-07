{{ config(materialized='table')}}
with customer_versions as (
    select customer_version_id AS customer_key, 
        customer_id, 
        inserted_at_dt AS valid_from, 
        LEAD(inserted_at_dt) OVER (
        PARTITION BY customer_id
        ORDER BY customer_version_id
        ) AS valid_to, 
        first_name, 
        last_name, 
        birth_date, 
        death_date, 
        registered_at_dt, 
        ingestion_run_id,
        updated_at_dt AS source_updated_at_dt   
    from {{ source('raw', 'customers') }}
)
select
    customer_key,
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
    valid_to is null as is_current
from customer_versions