-- Un client = une adresse e-mail normalisée. Les doublons (autre identifiant, e-mail écrit
-- autrement) sont regroupés sous le plus petit identifiant (customer_key).
with src as (
    select
        customer_id,
        lower(trim(email))          as email,
        cast(created_at as date)    as created_at,
        lower(trim(region))         as region_key
    from {{ source('raw', 'raw_customers') }}
)

select
    s.customer_id,
    s.email,
    s.created_at,
    min(s.customer_id) over (partition by s.email)  as customer_key,
    coalesce(m.region, 'Inconnue')                  as region
from src s
left join {{ ref('region_map') }} m on s.region_key = m.raw_value
