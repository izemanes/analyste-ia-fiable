select
    p.product_id,
    p.sku,
    p.product_name,
    coalesce(m.category, 'Autre')   as category,
    p.unit_cost_eur,
    p.list_price_ttc
from {{ source('raw', 'raw_products') }} p
left join {{ ref('category_map') }} m on lower(trim(p.category)) = m.raw_value
