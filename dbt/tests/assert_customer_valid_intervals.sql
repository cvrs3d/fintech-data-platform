select
    customer_key,
    customer_id,
    valid_from,
    valid_to,
    is_current
from {{ ref('dim_customer') }}
where valid_to <= valid_from
   or is_current is distinct from (valid_to is null)