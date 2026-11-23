{{ config(materialized='view') }}

select
    station_id,
    snapshot_date,
    operator_name,
    postal_code,
    city,
    federal_state,
    latitude,
    longitude,
    nominal_power_kw,
    connector_count,
    commissioned_date
from {{ source('raw', 'raw_stations_bnetza') }}
