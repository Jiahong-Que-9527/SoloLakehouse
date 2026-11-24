{{ config(
    materialized='table',
    **target_partition_config('revenue_date', 'date', ['country_code'])
) }}

-- fct_daily_revenue v1 (deprecated; see versions in schema.yml): core revenue only.
-- Grain (revenue_date, country_code, operator_name); operator resolves point-in-time
-- through station_sk -> dim_stations_scd2 (contract §2), so history never shifts
-- when operators change.

select
    f.revenue_date,
    f.country_code,
    d.operator_name,
    count(*) as session_count,
    cast(sum(f.energy_kwh) as {{ decimal_type(18, 4) }}) as total_energy_kwh,
    cast(sum(f.gross_amount_eur) as {{ decimal_type(18, 2) }}) as gross_amount_eur,
    cast(sum(f.roaming_fee_eur) as {{ decimal_type(18, 2) }}) as roaming_fee_eur,
    cast(sum(f.net_amount_eur) as {{ decimal_type(18, 2) }}) as net_amount_eur
from {{ ref('fct_charging_sessions') }} as f
inner join {{ ref('dim_stations_scd2') }} as d
    on d.dbt_scd_id = f.station_sk
-- The revenue window opens 2025-10-01 (contract §1, same bound dim_date uses).
-- Stated as a predicate so the BigQuery partition guard on fct_charging_sessions
-- can do partition elimination; it never excludes future partitions.
where f.revenue_date >= date '2025-10-01'
group by f.revenue_date, f.country_code, d.operator_name
