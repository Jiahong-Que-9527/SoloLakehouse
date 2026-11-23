{{ config(materialized='view') }}

-- Current-state tariff dimension: a view over the SCD2 history (contract §2
-- build-order note). tariff_sk is the snapshot surrogate key (dbt_scd_id).

select
    dbt_scd_id as tariff_sk,
    tariff_id,
    plan_tier,
    price_per_kwh_eur,
    roaming_surcharge_eur,
    dbt_valid_from,
    dbt_valid_to
from {{ ref('dim_tariffs_scd2') }}
where dbt_valid_to is null
