{{ config(materialized='view') }}

select
    timestamp_utc,
    market_zone,
    wholesale_eur_mwh,
    grid_load_mwh
from {{ source('raw', 'raw_smard_prices') }}
