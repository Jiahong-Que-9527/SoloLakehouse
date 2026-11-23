-- Canonical revenue conservation (data-contract v1.3 §3.1):
--   SUM(net_amount_eur recomputed from valid raw events, latest event per session)
--     == SUM(fct_charging_sessions.net_amount_eur),  tolerance 0.00 EUR.
-- Quarantined rows never reached raw, so the reduction below runs over valid
-- events only. The FX and fee joins here are an independent recomputation —
-- deliberately not reading int_sessions_enriched_fx or the marts' own pipeline.

with reduced as (
    select
        l.session_id,
        l.currency_code,
        l.gross_amount_local,
        {{ to_berlin_date('l.session_started_at') }} as revenue_date
    from {{ ref('int_sessions_latest') }} as l
),

fees as (
    select
        r.session_id,
        sum(r.roaming_fee_local) as roaming_fee_local
    from {{ ref('stg_roaming_settlements') }} as r
    group by r.session_id
),

fx as (
    select
        s.session_id,
        coalesce(f.rate, cast(1.0 as decimal(12, 6))) as fx_rate_to_eur
    from reduced as s
    left join {{ ref('stg_ecb_fx') }} as f
        on
            f.currency_pair = 'EUR/' || s.currency_code
            and f.observation_date <= s.revenue_date
    qualify row_number() over (
        partition by s.session_id
        order by f.observation_date desc
    ) = 1
),

recomputed as (
    select
        sum(
            cast(round(x.gross_amount_local / x2.fx_rate_to_eur, 2) as decimal(18, 2))
            + cast(
                round(
                    coalesce(fe.roaming_fee_local, cast(0.0 as decimal(12, 2)))
                    / x2.fx_rate_to_eur,
                    2
                ) as decimal(18, 2)
            )
        ) as net_total
    from reduced as x
    inner join fx as x2
        on x2.session_id = x.session_id
    left join fees as fe
        on fe.session_id = x.session_id
),

mart as (
    select sum(m.net_amount_eur) as net_total
    from {{ ref('fct_charging_sessions') }} as m
)

select
    recomputed.net_total as recomputed_net_eur,
    mart.net_total as mart_net_eur
from recomputed
cross join mart
where
    recomputed.net_total is null
    or mart.net_total is null
    or abs(recomputed.net_total - mart.net_total) > 0.00
