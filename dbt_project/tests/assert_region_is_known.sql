-- Toute région du mart doit appartenir à la liste officielle (ou « Inconnue »).
select customer_key, region
from {{ ref('dim_customers') }}
where region not in (
    'Île-de-France', 'Auvergne-Rhône-Alpes', 'Provence-Alpes-Côte d''Azur', 'Occitanie',
    'Nouvelle-Aquitaine', 'Bretagne', 'Hauts-de-France', 'Grand Est', 'Inconnue'
)
