{{ config(materialized='view') }}

-- Exactly one row per session: the binding latest-event reduction (contract §3.2).
-- Ties on event_seq (same event ingested more than once under different hashes)
-- resolve by _ingested_at, then _source_hash, for determinism.

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
    _batch_id,
    _ingested_at,
    _source_name,
    _source_hash
from {{ ref('stg_charging_sessions') }}
qualify row_number() over (
    partition by session_id
    order by event_seq desc, _ingested_at desc, _source_hash desc
) = 1
