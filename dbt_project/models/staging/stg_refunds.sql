select
    r.refund_id,
    r.order_item_id,
    r.quantity_returned,
    cast(r.refund_date as date)                 as refund_date,
    r.quantity_returned * i.unit_net_ht         as refunded_ht
from {{ source('raw', 'raw_refunds') }} r
join {{ ref('stg_order_items') }} i using (order_item_id)
