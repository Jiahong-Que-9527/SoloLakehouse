{{ config(materialized='table') }}

-- Current-state station dimension, built from the latest raw snapshot (t2) until
-- E04 turns it into a view over dim_stations_scd2 (contract §2 build-order note).
-- dbt_valid_from is pinned to the t0 snapshot date; dbt_valid_to stays null.

with latest as (
    select
        b.station_id,
        b.operator_name,
        b.city,
        b.federal_state,
        b.postal_code,
        b.nominal_power_kw,
        b.connector_count
    from {{ ref('stg_bnetza_stations') }} as b
    where b.snapshot_date = (
        select max(b2.snapshot_date)
        from {{ ref('stg_bnetza_stations') }} as b2
    )
)

select
    row_number() over (order by l.station_id) as station_sk,
    l.station_id,
    l.operator_name,
    l.city,
    l.federal_state,
    l.postal_code,
    l.nominal_power_kw,
    l.connector_count,
    (
        select min(b3.snapshot_date)
        from {{ ref('stg_bnetza_stations') }} as b3
    ) as dbt_valid_from,
    cast(null as date) as dbt_valid_to
from latest as l
