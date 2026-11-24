-- ECB Daily FX Summary Mart: grain (rate_date, currency_pair) with the rate,
-- the previous day's rate and the day-over-day change. Window over the typed
-- staging view; the change is legitimately null on each pair's first
-- observation (no previous day), which the enforced contract reflects.

with typed as (
    select
        rate_date,
        currency_pair,
        rate
    from {{ ref('stg_ecb_fx_rates') }}
),

windowed as (
    select
        *,
        lag(rate) over (
            partition by currency_pair order by rate_date
        ) as prev_rate
    from typed
)

select
    rate_date,
    currency_pair,
    rate,
    prev_rate,
    cast(rate - prev_rate as decimal(18, 6)) as day_over_day_change
from windowed
