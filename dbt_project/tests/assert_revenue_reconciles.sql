-- Rapprochement : le CA net de la table de faits doit égaler un recalcul direct sur les tables brutes
-- (formulation différente, sans passer par les modèles dbt). Tolérance : 1 centime.
with direct_calc as (
    select
        sum(i.quantity * i.unit_price_ttc * (1 - i.discount_pct) / (1 + i.vat_rate))
        - coalesce((
            select sum(r.quantity_returned * i2.unit_price_ttc * (1 - i2.discount_pct) / (1 + i2.vat_rate))
            from {{ source('raw', 'raw_refunds') }} r
            join {{ source('raw', 'raw_order_items') }} i2 using (order_item_id)
            join {{ source('raw', 'raw_orders') }} o2 using (order_id)
            where o2.status in ('DLV', 'SHP', 'PAID')
        ), 0) as revenue
    from {{ source('raw', 'raw_order_items') }} i
    join {{ source('raw', 'raw_orders') }} o using (order_id)
    where o.status in ('DLV', 'SHP', 'PAID')
),
modeled as (
    select sum(net_ht) as revenue from {{ ref('fct_order_lines') }}
)
select d.revenue as direct_revenue, m.revenue as modeled_revenue
from direct_calc d, modeled m
where abs(d.revenue - m.revenue) > 0.01
