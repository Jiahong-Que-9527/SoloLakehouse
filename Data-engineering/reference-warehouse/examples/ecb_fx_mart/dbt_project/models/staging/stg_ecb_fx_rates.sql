-- Staging: typed 1:1 over the ECB seed drop (template pattern).

select
    cast(observation_date as date) as rate_date,
    cast(currency_pair as varchar) as currency_pair,
    cast(rate as decimal(18, 6)) as rate
from {{ ref('ecb_fx_rates') }}
