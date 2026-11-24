{% snapshot dim_tariffs_scd2 %}

{{
    config(
        target_schema=snapshot_target_schema(),
        unique_key='tariff_id',
        strategy='timestamp',
        updated_at='updated_at',
        invalidate_hard_deletes=False,
    )
}}

-- SCD Type 2 history for tariffs, driven by the raw t0/t1/t2 snapshot dates as
-- simulated time (ADR-0002). Tracked attributes: price_per_kwh_eur,
-- roaming_surcharge_eur, plan_tier. updated_at = the earliest raw snapshot date
-- at which the tariff's tracked attributes equal the as-of values (idempotent
-- across repeated runs, see dim_stations_scd2 for the full rationale).

with current_snapshot as (
    select *
    from {{ ref('stg_tariff_plans') }}
    where snapshot_date = cast('{{ var("snapshot_asof", "2026-05-15") }}' as date)
)

select
    t.tariff_id,
    t.plan_tier,
    t.price_per_kwh_eur,
    t.roaming_surcharge_eur,
    (
        select min(h.snapshot_date)
        from {{ ref('stg_tariff_plans') }} as h
        where h.tariff_id = t.tariff_id
            and h.snapshot_date <= t.snapshot_date
            and h.price_per_kwh_eur is not distinct from t.price_per_kwh_eur
            and h.roaming_surcharge_eur is not distinct from t.roaming_surcharge_eur
            and h.plan_tier is not distinct from t.plan_tier
    ) as updated_at
from current_snapshot as t

{% endsnapshot %}
