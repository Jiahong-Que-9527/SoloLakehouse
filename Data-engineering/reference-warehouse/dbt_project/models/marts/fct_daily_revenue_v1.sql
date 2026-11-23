{{ config(materialized='table') }}

-- fct_daily_revenue v1 (deprecated; see versions in schema.yml): core revenue only.
-- Grain (revenue_date, country_code, operator_name); operator resolves through
-- station_sk -> dim_stations (point-in-time via SCD2 from E04 onward, contract §2).

select
    f.revenue_date,
    f.country_code,
    d.operator_name,
    count(*) as session_count,
    cast(sum(f.energy_kwh) as decimal(18, 4)) as total_energy_kwh,
    cast(sum(f.gross_amount_eur) as decimal(18, 2)) as gross_amount_eur,
    cast(sum(f.roaming_fee_eur) as decimal(18, 2)) as roaming_fee_eur,
    cast(sum(f.net_amount_eur) as decimal(18, 2)) as net_amount_eur
from {{ ref('fct_charging_sessions') }} as f
inner join {{ ref('dim_stations') }} as d
    on d.station_sk = f.station_sk
group by f.revenue_date, f.country_code, d.operator_name
