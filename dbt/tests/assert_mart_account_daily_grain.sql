select 
    count(*),
    activity_date, 
    account_id, 
    currency_key
from {{ ref('mart_account_daily') }}
group by activity_date, account_id, currency_key
having count(*) > 1