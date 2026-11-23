{{ config(materialized='view') }}

-- Adds revenue_date (Europe/Berlin civil date, contract §3.4), the ECB FX rate in
-- force at revenue_date (carry-forward, never lookahead — §3.7) and the billed
-- roaming fee (0.00 when no settlement row exists — §2).

with sessions as (
    select
        *,
        {{ to_berlin_date('session_started_at') }} as revenue_date
    from {{ ref('int_sessions_latest') }}
),

roaming_fees as (
    select
        session_id,
        sum(roaming_fee_local) as roaming_fee_local
    from {{ ref('stg_roaming_settlements') }}
    group by session_id
),

fx_lookup as (
    select
        s.session_id,
        s.revenue_date,
        s.currency_code,
        coalesce(f.rate, cast(1.0 as decimal(12, 6))) as fx_rate_to_eur,
        case
            when s.currency_code = 'EUR' then 'observed'
            when f.observation_date = s.revenue_date then 'observed'
            else 'carried_forward'
        end as fx_rate_status
    from sessions s
    left join {{ ref('stg_ecb_fx') }} f
        on f.currency_pair = 'EUR/' || s.currency_code
        and f.observation_date <= s.revenue_date
    qualify row_number() over (
        partition by s.session_id
        order by f.observation_date desc
    ) = 1
)

select
    s.session_id,
    s.event_seq,
    s.station_id,
    s.tariff_id,
    s.country_code,
    s.currency_code,
    s.revenue_date,
    fx.fx_rate_to_eur,
    fx.fx_rate_status,
    s.session_started_at,
    s.session_ended_at,
    s.settled_at,
    s.energy_kwh,
    s.gross_amount_local,
    coalesce(r.roaming_fee_local, cast(0.0 as decimal(12, 2))) as roaming_fee_local,
    s.event_type
from sessions s
join fx_lookup fx on fx.session_id = s.session_id
left join roaming_fees r on r.session_id = s.session_id
