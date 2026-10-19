-- Aucune commande annulée ou de test ne doit entrer dans la table de faits.
select f.order_id
from {{ ref('fct_order_lines') }} f
join {{ source('raw', 'raw_orders') }} o using (order_id)
where o.status in ('CXL', 'TST')
