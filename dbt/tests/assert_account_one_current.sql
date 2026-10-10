select account_id, 
    count(*) filter (where is_current)
from {{ ref ('dim_account') }}
group by account_id
having count(*) filter (where is_current) <> 1