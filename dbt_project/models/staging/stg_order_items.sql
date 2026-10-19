-- Prix HT net de remise = prix TTC * (1 - remise) / (1 + TVA)
select
    order_item_id,
    order_id,
    product_id,
    quantity,
    unit_price_ttc,
    discount_pct,
    vat_rate,
    unit_price_ttc * (1 - discount_pct) / (1 + vat_rate)              as unit_net_ht,
    quantity * unit_price_ttc * (1 - discount_pct) / (1 + vat_rate)   as gross_ht
from {{ source('raw', 'raw_order_items') }}
