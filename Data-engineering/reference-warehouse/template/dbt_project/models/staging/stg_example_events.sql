-- Staging: typed, 1:1 over the raw drop (seed here; swap in your ingest
-- pipeline later). Rename per your domain convention stg_<domain>_<entity>.

select
    cast(date as date) as event_date,
    cast(region as varchar) as region,
    cast(amount_eur as decimal(18, 2)) as amount_eur
from {{ ref('raw_events') }}
