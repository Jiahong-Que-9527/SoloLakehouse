{{ config(materialized='view') }}

-- Prices each session with the DE-LU SMARD slot containing session_started_at (UTC),
-- per contract §3.8: the latest slot with timestamp_utc <= session_started_at.
-- After-window sessions therefore pick up the latest available slot automatically;
-- before-window sessions (unreachable in the locked window, guarded by the E03
-- assert_no_session_outside_price_window singular test) fall back to the earliest
-- available price.

with prices as (
    select timestamp_utc, wholesale_eur_mwh
    from {{ ref('stg_smard_prices') }}
    where market_zone = 'DE-LU'
),

priced as (
    select
        s.session_id,
        p.wholesale_eur_mwh as slot_price
    from {{ ref('int_sessions_enriched_fx') }} s
    left join prices p
        on p.timestamp_utc <= s.session_started_at
    qualify row_number() over (
        partition by s.session_id
        order by p.timestamp_utc desc
    ) = 1
),

boundary as (
    select
        (select wholesale_eur_mwh from prices order by timestamp_utc asc limit 1) as earliest_price
)

select
    s.*,
    coalesce(p.slot_price, b.earliest_price) as wholesale_eur_mwh,
    round(s.energy_kwh * coalesce(p.slot_price, b.earliest_price) / 1000, 2) as wholesale_cost_eur
from {{ ref('int_sessions_enriched_fx') }} s
join priced p on p.session_id = s.session_id
cross join boundary b
