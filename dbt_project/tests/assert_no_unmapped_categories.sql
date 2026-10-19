select p.product_id, p.category
from {{ source('raw', 'raw_products') }} p
join {{ ref('stg_products') }} s using (product_id)
where s.category = 'Autre'
