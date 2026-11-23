{{ config(materialized='view') }}

-- 1:1 with raw except byte-identical duplicate payloads (same business values and
-- _source_hash), which are dropped here per contract §3.2 — never quarantined.
-- Lineage columns _batch_id/_ingested_at may differ between duplicates; min() keeps
-- the reduction deterministic.

select
    session_id,
    event_seq,
    station_id,
    tariff_id,
    country_code,
    currency_code,
    session_started_at,
    session_ended_at,
    settled_at,
    energy_kwh,
    gross_amount_local,
    event_type,
    min(_batch_id) as _batch_id,
    min(_ingested_at) as _ingested_at,
    _source_name,
    _source_hash
from {{ source('raw', 'raw_charging_sessions') }}
group by
    session_id,
    event_seq,
    station_id,
    tariff_id,
    country_code,
    currency_code,
    session_started_at,
    session_ended_at,
    settled_at,
    energy_kwh,
    gross_amount_local,
    event_type,
    _source_name,
    _source_hash
