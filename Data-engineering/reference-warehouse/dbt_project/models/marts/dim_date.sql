{{ config(materialized='table') }}

-- Date dimension over the locked session/price window (2025-10-01 .. 2026-05-31).
-- German public holidays (nationwide + Hessen) are a frozen list for this window:
-- the ECB calendar only covers TARGET2, and per-state holiday sources are an E02
-- decision recorded in the acceptance evidence.

with spine as (
    {{ date_spine('2025-10-01', '2026-05-31') }}
),

holidays as (
    -- Gesetzliche Feiertage (Bund + Hessen) within the window.
    -- Union-all form keeps this portable: BigQuery rejects both the
    -- `cte (colname) as` column list and the standalone VALUES clause.
    select date '2025-10-03' as date_day  -- Tag der Deutschen Einheit
    union all
    select date '2025-12-25'    -- 1. Weihnachtstag
    union all
    select date '2025-12-26'    -- 2. Weihnachtstag
    union all
    select date '2026-01-01'    -- Neujahr
    union all
    select date '2026-04-03'    -- Karfreitag
    union all
    select date '2026-04-06'    -- Ostermontag
    union all
    select date '2026-05-01'    -- Tag der Arbeit
    union all
    select date '2026-05-14'    -- Christi Himmelfahrt
    union all
    select date '2026-05-25'    -- Pfingstmontag
)

select
    s.date_day,
    extract(year from s.date_day) as year_num,
    extract(month from s.date_day) as month_num,
    {{ iso_day_of_week('s.date_day') }} as day_of_week,
    {{ iso_day_of_week('s.date_day') }} in (6, 7) as is_weekend,
    s.date_day in (
        select h.date_day from holidays as h
    ) as is_de_holiday
from spine as s
