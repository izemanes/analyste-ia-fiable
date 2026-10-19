-- Table de faits : une ligne de commande VALIDE (livrée, expédiée ou payée).
-- Le chiffre d'affaires est net : HT, après remise, après retours (rattachés à la date de commande).
-- Le coût des produits retournés est supposé remis en stock (donc retiré du coût des ventes).
with refunds as (
    select
        order_item_id,
        sum(quantity_returned)  as refunded_qty,
        sum(refunded_ht)        as refunded_ht
    from {{ ref('stg_refunds') }}
    group by 1
)

select
    i.order_item_id,
    o.order_id,
    o.order_date,
    strftime(o.order_date, '%Y-%m')                                             as order_month,
    cast(strftime(o.order_date, '%Y') as integer)                               as order_year,
    strftime(o.order_date, '%Y') || '-Q' || cast(quarter(o.order_date) as varchar) as order_quarter,
    c.customer_key,
    d.region,
    o.channel,
    i.product_id,
    p.product_name,
    p.category,
    i.quantity,
    i.gross_ht,
    coalesce(r.refunded_qty, 0)                                                 as refunded_qty,
    coalesce(r.refunded_ht, 0)                                                  as refunded_ht,
    i.gross_ht - coalesce(r.refunded_ht, 0)                                     as net_ht,
    (i.quantity - coalesce(r.refunded_qty, 0)) * p.unit_cost_eur                as cogs_net
from {{ ref('stg_order_items') }} i
join {{ ref('stg_orders') }} o using (order_id)
join {{ ref('stg_customers') }} c on o.customer_id = c.customer_id
join {{ ref('dim_customers') }} d on c.customer_key = d.customer_key
join {{ ref('stg_products') }} p using (product_id)
left join refunds r using (order_item_id)
where o.is_valid
