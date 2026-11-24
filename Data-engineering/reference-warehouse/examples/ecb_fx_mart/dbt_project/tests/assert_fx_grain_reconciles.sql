-- Reconciliation: the mart is a 1:1 enrichment of the staging series, so its
-- grain must preserve the staging row count exactly (no dropped days, no
-- duplicated pairs). Mirrors the primary warehouse's reconciliation pattern
-- (fact vs raw grain, E02).
--
-- (An earlier draft asserted max-gap <= one weekend; real ECB publications
-- also skip public holidays, which pushes individual gaps past three days —
-- the reconciliation test below is the invariant that actually holds.)

select
    s.staged_rows,
    m.mart_rows
from
    (select count(*) as staged_rows from {{ ref('stg_ecb_fx_rates') }}) as s,
    (select count(*) as mart_rows from {{ ref('fct_fx_rates_daily') }}) as m
where s.staged_rows != m.mart_rows
