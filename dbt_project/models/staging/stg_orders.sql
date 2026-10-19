-- Statuts source : DLV livrée, SHP expédiée, PAID payée, CXL annulée, TST test interne.
-- Une commande est « valide » (comptée dans les chiffres) si elle est livrée, expédiée ou payée.
select
    order_id,
    customer_id,
    cast(order_date as date)                    as order_date,
    status,
    channel,
    status in ('DLV', 'SHP', 'PAID')            as is_valid
from {{ source('raw', 'raw_orders') }}
