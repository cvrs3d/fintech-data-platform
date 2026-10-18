select
    e.entry_id as source_entry_id,
    f.entry_id as fact_entry_id
from {{ ref('stg_entries') }} as e
full outer join {{ ref('fact_entries') }} as f
    on e.entry_id = f.entry_id
where e.entry_id is null
   or f.entry_id is null