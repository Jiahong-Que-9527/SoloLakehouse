{{ config(materialized='table') }}

-- Current-state tariff dimension, built from the latest raw snapshot (t2) until
-- E04 turns it into a view over dim_tariffs_scd2 (contract §2 build-order note).

{% set tariffs %}{{ ref('stg_tariff_plans') }}{% endset %}

with latest as (
    select *
    from {{ tariffs }}
    where snapshot_date = (select max(snapshot_date) from {{ tariffs }})
)

select
    row_number() over (order by tariff_id) as tariff_sk,
    tariff_id,
    plan_tier,
    price_per_kwh_eur,
    roaming_surcharge_eur,
    (select min(snapshot_date) from {{ tariffs }}) as dbt_valid_from,
    cast(null as date) as dbt_valid_to
from latest
