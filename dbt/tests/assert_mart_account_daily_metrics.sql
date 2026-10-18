select
    activity_date,
    account_id,
    currency_key,
    entries_count,
    incoming_amount,
    outgoing_amount,
    net_amount
from {{ ref('mart_account_daily') }}
where entries_count <= 0
    or (
        currency_key is null
        and (
            incoming_amount is not null
            or outgoing_amount is not null
            or net_amount is not null
        )
    )
    or (
        currency_key is not null
        and (
            incoming_amount is null
            or outgoing_amount is null
            or net_amount is null
            or incoming_amount < 0
            or outgoing_amount < 0
            or net_amount is distinct from (
                incoming_amount - outgoing_amount
            )
        )
    )