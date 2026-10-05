select *
from {{ ref('stg_entries') }}
where entry_id is null
   or amount = 0
   or amount is null