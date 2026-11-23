{{ config(materialized='view') }}

select
    currency_pair,
    observation_date,
    rate
from {{ source('raw', 'raw_ecb_fx_rates') }}
