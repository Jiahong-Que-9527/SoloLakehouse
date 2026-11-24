{% snapshot dim_stations_scd2 %}

{{
    config(
        target_schema=('de_mart' if target.type == 'bigquery' else 'mart'),
        unique_key='station_id',
        strategy='timestamp',
        updated_at='updated_at',
        invalidate_hard_deletes=False,
    )
}}

-- SCD Type 2 history for stations, driven by the raw t0/t1/t2 snapshot dates as
-- simulated time (ADR-0002): dbt_valid_from/to become the snapshot dates, so the
-- point-in-time fact join works for historical sessions.
--
-- updated_at = the earliest raw snapshot date at which the station's tracked
-- attributes equal the as-of values. This makes repeated runs at the same or
-- later as-of dates idempotent: unchanged stations keep their original
-- updated_at, so the timestamp strategy never churns them.

with current_snapshot as (
    select *
    from {{ ref('stg_bnetza_stations') }}
    where snapshot_date = cast('{{ var("snapshot_asof", "2026-05-15") }}' as date)
)

select
    s.station_id,
    s.operator_name,
    s.city,
    s.federal_state,
    s.postal_code,
    s.nominal_power_kw,
    s.connector_count,
    s.commissioned_date,
    (
        select min(h.snapshot_date)
        from {{ ref('stg_bnetza_stations') }} as h
        where h.station_id = s.station_id
            and h.snapshot_date <= s.snapshot_date
            and h.operator_name is not distinct from s.operator_name
            and h.nominal_power_kw is not distinct from s.nominal_power_kw
            and h.connector_count is not distinct from s.connector_count
    ) as updated_at
from current_snapshot as s

{% endsnapshot %}
