{{ config(materialized='table') }}

-- Session fact at grain (session_id), built from int_sessions_wholesale_cost
-- (one row per session by construction). Amounts follow contract §3.3: each EUR
-- column is derived from raw values with a single rounding; net and margin are
-- exact additions/subtractions of 2-decimal components (no re-rounding).

with sessions as (
    select * from {{ ref('int_sessions_wholesale_cost') }}
),

amounts as (
    select
        s.*,
        round(s.gross_amount_local / s.fx_rate_to_eur, 2) as gross_amount_eur,
        round(s.roaming_fee_local / s.fx_rate_to_eur, 2) as roaming_fee_eur
    from sessions s
)

select
    a.session_id,
    st.station_sk,
    ta.tariff_sk,
    a.revenue_date,
    a.country_code,
    a.currency_code,
    a.fx_rate_to_eur,
    a.fx_rate_status,
    a.energy_kwh,
    a.gross_amount_eur,
    a.roaming_fee_eur,
    a.gross_amount_eur + a.roaming_fee_eur as net_amount_eur,
    a.wholesale_cost_eur,
    a.gross_amount_eur + a.roaming_fee_eur - a.wholesale_cost_eur as gross_margin_eur,
    a.event_type,
    a.settled_at
from amounts a
join {{ ref('dim_stations') }} st on st.station_id = a.station_id
join {{ ref('dim_tariffs') }} ta on ta.tariff_id = a.tariff_id
