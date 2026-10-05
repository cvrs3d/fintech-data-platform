select
    transaction_id,
    count(*) as entry_count,
    count(distinct account_id) as account_count,
    sum(amount) as net_amount
from {{ ref('stg_entries') }}
group by transaction_id
having count(*) <> 2
    or count(distinct account_id) <> 2
    or sum(amount) <> 0