-- Un enregistrement par client réel (doublons fusionnés).
select
    customer_key,
    email,
    created_at,
    region
from {{ ref('stg_customers') }}
where customer_id = customer_key
