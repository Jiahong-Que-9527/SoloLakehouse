{{ config(materialized='table') }}

-- Date dimension over the locked session/price window (2025-10-01 .. 2026-05-31).
-- German public holidays (nationwide + Hessen) are a frozen list for this window:
-- the ECB calendar only covers TARGET2, and per-state holiday sources are an E02
-- decision recorded in the acceptance evidence.

with spine as (
    {{ date_spine('2025-10-01', '2026-05-31') }}
),

holidays (date_day) as (
    -- Gesetzliche Feiertage (Bund + Hessen) within the window
    values
    (date '2025-10-03'),  -- Tag der Deutschen Einheit
    (date '2025-12-25'),  -- 1. Weihnachtstag
    (date '2025-12-26'),  -- 2. Weihnachtstag
    (date '2026-01-01'),  -- Neujahr
    (date '2026-04-03'),  -- Karfreitag
    (date '2026-04-06'),  -- Ostermontag
    (date '2026-05-01'),  -- Tag der Arbeit
    (date '2026-05-14'),  -- Christi Himmelfahrt
    (date '2026-05-25')   -- Pfingstmontag
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
