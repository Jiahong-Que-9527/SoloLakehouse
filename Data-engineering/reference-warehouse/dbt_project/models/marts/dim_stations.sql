{{ config(materialized='table') }}

-- Current-state station dimension, built from the latest raw snapshot (t2) until
-- E04 turns it into a view over dim_stations_scd2 (contract §2 build-order note).
-- dbt_valid_from is pinned to the t0 snapshot date; dbt_valid_to stays null.

{% set stations %}{{ ref('stg_bnetza_stations') }}{% endset %}

with latest as (
    select *
    from {{ stations }}
    where snapshot_date = (select max(snapshot_date) from {{ stations }})
)

select
    row_number() over (order by station_id) as station_sk,
    station_id,
    operator_name,
    city,
    federal_state,
    postal_code,
    nominal_power_kw,
    connector_count,
    (select min(snapshot_date) from {{ stations }}) as dbt_valid_from,
    cast(null as date) as dbt_valid_to
from latest
