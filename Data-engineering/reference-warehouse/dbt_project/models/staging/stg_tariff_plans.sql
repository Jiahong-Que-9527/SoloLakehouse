{{ config(materialized='view') }}

select
    tariff_id,
    snapshot_date,
    price_per_kwh_eur,
    roaming_surcharge_eur,
    plan_tier
from {{ source('raw', 'raw_tariff_plans') }}
