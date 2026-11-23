{{ config(materialized='table') }}

-- Current-state tariff dimension, built from the latest raw snapshot (t2) until
-- E04 turns it into a view over dim_tariffs_scd2 (contract §2 build-order note).

with latest as (
    select
        t.tariff_id,
        t.plan_tier,
        t.price_per_kwh_eur,
        t.roaming_surcharge_eur
    from {{ ref('stg_tariff_plans') }} as t
    where t.snapshot_date = (
        select max(t2.snapshot_date)
        from {{ ref('stg_tariff_plans') }} as t2
    )
)

select
    row_number() over (order by l.tariff_id) as tariff_sk,
    l.tariff_id,
    l.plan_tier,
    l.price_per_kwh_eur,
    l.roaming_surcharge_eur,
    (
        select min(t3.snapshot_date)
        from {{ ref('stg_tariff_plans') }} as t3
    ) as dbt_valid_from,
    cast(null as date) as dbt_valid_to
from latest as l
