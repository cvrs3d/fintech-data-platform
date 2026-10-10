select 
    account_id,
    account_key,
    valid_from,
    valid_to,
    is_current
from {{ ref('dim_account') }}
where valid_to <= valid_from
    or is_current is distinct from (valid_to is null)
