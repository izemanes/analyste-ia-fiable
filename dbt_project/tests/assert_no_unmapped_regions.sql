-- Échoue si une région présente dans la source n'est pas reconnue par le seed region_map.
select r.customer_id, r.region
from {{ source('raw', 'raw_customers') }} r
join {{ ref('stg_customers') }} s using (customer_id)
where r.region is not null and s.region = 'Inconnue'
