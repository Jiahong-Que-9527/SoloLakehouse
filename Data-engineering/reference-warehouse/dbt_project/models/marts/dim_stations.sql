{{ config(materialized='view') }}

-- Current-state station dimension: a view over the SCD2 history (contract §2
-- build-order note). station_sk is the snapshot surrogate key (dbt_scd_id).

select
    dbt_scd_id as station_sk,
    station_id,
    operator_name,
    city,
    federal_state,
    postal_code,
    nominal_power_kw,
    connector_count,
    dbt_valid_from,
    dbt_valid_to
from {{ ref('dim_stations_scd2') }}
where dbt_valid_to is null
