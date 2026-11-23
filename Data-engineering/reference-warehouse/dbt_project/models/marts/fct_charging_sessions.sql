{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='session_id',
    on_schema_change='fail',
    **target_partition_config('revenue_date', 'date', ['country_code', 'station_sk']),
) }}

-- Session fact at grain (session_id), incremental merge per contract §3.5:
-- the merge source is the recomputed int_sessions_latest row (whole-row
-- replacement; per-event upserts are forbidden). Incoming sessions are
-- filtered by a 48-hour settled_at lookback, overridable with bounded
-- backfill vars. Point-in-time joins (§3.6) attach the station/tariff
-- version valid at session_started_at, so historical revenue never shifts.

with sessions as (
    select
        w.*,
        {{ eur_currency_convert('w.gross_amount_local', 'w.fx_rate_to_eur') }} as gross_amount_eur,
        {{ eur_currency_convert('w.roaming_fee_local', 'w.fx_rate_to_eur') }} as roaming_fee_eur
    from {{ ref('int_sessions_wholesale_cost') }} as w
    {% if is_incremental() %}
        {{ incremental_lookback_filter('w.settled_at', 2) }}
    {% endif %}
)

select
    a.session_id,
    st.dbt_scd_id as station_sk,
    ta.dbt_scd_id as tariff_sk,
    a.revenue_date,
    a.country_code,
    a.currency_code,
    a.fx_rate_to_eur,
    a.fx_rate_status,
    a.energy_kwh,
    a.gross_amount_eur,
    a.roaming_fee_eur,
    cast(a.gross_amount_eur + a.roaming_fee_eur as decimal(18, 2)) as net_amount_eur,
    a.wholesale_cost_eur,
    cast(
        a.gross_amount_eur + a.roaming_fee_eur - a.wholesale_cost_eur as decimal(18, 2)
    ) as gross_margin_eur,
    a.event_type,
    a.settled_at
from sessions as a
inner join {{ ref('dim_stations_scd2') }} as st
    on
        st.station_id = a.station_id
        and a.session_started_at >= st.dbt_valid_from
        and (
            st.dbt_valid_to is null
            or a.session_started_at < st.dbt_valid_to
        )
inner join {{ ref('dim_tariffs_scd2') }} as ta
    on
        ta.tariff_id = a.tariff_id
        and a.session_started_at >= ta.dbt_valid_from
        and (
            ta.dbt_valid_to is null
            or a.session_started_at < ta.dbt_valid_to
        )
