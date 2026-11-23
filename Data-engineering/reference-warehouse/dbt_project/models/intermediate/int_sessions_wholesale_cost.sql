{{ config(materialized='view') }}

-- Prices each session with the DE-LU SMARD slot containing session_started_at (UTC),
-- per contract §3.8: the latest slot with timestamp_utc <= session_started_at.
-- After-window sessions therefore pick up the latest available slot automatically;
-- before-window sessions (unreachable in the locked window, guarded by the E03
-- assert_no_session_outside_price_window singular test) fall back to the earliest
-- available price.

with prices as (
    select
        p.timestamp_utc,
        p.wholesale_eur_mwh
    from {{ ref('stg_smard_prices') }} as p
    where p.market_zone = 'DE-LU'
),

priced as (
    select
        s.session_id,
        p.wholesale_eur_mwh as slot_price
    from {{ ref('int_sessions_enriched_fx') }} as s
    left join prices as p
        on s.session_started_at >= p.timestamp_utc
    qualify row_number() over (
        partition by s.session_id
        order by p.timestamp_utc desc
    ) = 1
),

boundary as (
    select
        (
            select pb.wholesale_eur_mwh
            from prices as pb
            order by pb.timestamp_utc asc
            limit 1
        ) as earliest_price
)

select
    s.*,
    coalesce(p.slot_price, b.earliest_price) as wholesale_eur_mwh,
    -- Contract §2: wholesale cost carries the sign of the event — negative for
    -- refunds (the revenue reversal mirrors the energy cost), positive otherwise.
    -- Physical energy stays >= 0 even on refunds, so the sign comes from event_type.
    cast(
        round(s.energy_kwh * coalesce(p.slot_price, b.earliest_price) / 1000, 2)
        * case when s.event_type = 'refund' then -1 else 1 end
        as decimal(18, 2)
    ) as wholesale_cost_eur
from {{ ref('int_sessions_enriched_fx') }} as s
inner join priced as p
    on p.session_id = s.session_id
cross join boundary as b
