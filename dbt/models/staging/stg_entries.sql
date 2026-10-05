{{ config(materialized='view') }}
select entry_id, transaction_id, account_id, amount, created_at_dt, executed_at_dt, inserted_at_dt, ingestion_run_id
from {{ source('raw', 'entries') }}
