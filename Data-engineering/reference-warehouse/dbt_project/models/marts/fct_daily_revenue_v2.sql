{{ config(materialized='table') }}

-- fct_daily_revenue v2 (latest): non-breaking additive change per contract §2 —
-- adds wholesale_cost_eur and gross_margin_eur on top of the v1 column set.

select
    f.revenue_date,
    f.country_code,
    d.operator_name,
    count(*) as session_count,
    cast(sum(f.energy_kwh) as decimal(18, 4)) as total_energy_kwh,
    cast(sum(f.gross_amount_eur) as decimal(18, 2)) as gross_amount_eur,
    cast(sum(f.roaming_fee_eur) as decimal(18, 2)) as roaming_fee_eur,
    cast(sum(f.net_amount_eur) as decimal(18, 2)) as net_amount_eur,
    cast(sum(f.wholesale_cost_eur) as decimal(18, 2)) as wholesale_cost_eur,
    cast(sum(f.gross_margin_eur) as decimal(18, 2)) as gross_margin_eur
from {{ ref('fct_charging_sessions') }} as f
inner join {{ ref('dim_stations_scd2') }} as d
    on d.dbt_scd_id = f.station_sk
group by f.revenue_date, f.country_code, d.operator_name
