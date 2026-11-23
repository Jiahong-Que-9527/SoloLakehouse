{{ config(materialized='table') }}

-- Daily revenue at grain (revenue_date, country_code, operator_name).
-- operator_name resolves through station_sk -> dim_stations (point-in-time via
-- SCD2 from E04 onward, contract §2), so history never shifts when operators change.

select
    f.revenue_date,
    f.country_code,
    d.operator_name,
    count(*) as session_count,
    sum(f.energy_kwh) as total_energy_kwh,
    sum(f.gross_amount_eur) as gross_amount_eur,
    sum(f.roaming_fee_eur) as roaming_fee_eur,
    sum(f.net_amount_eur) as net_amount_eur
from {{ ref('fct_charging_sessions') }} as f
inner join {{ ref('dim_stations') }} as d
    on d.station_sk = f.station_sk
group by f.revenue_date, f.country_code, d.operator_name
