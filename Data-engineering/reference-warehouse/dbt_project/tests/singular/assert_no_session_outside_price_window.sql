-- Contract §3.8 guard: every session must find the DE-LU SMARD slot containing
-- session_started_at. A row here means the §3.8 boundary fallback was exercised —
-- unreachable within the locked fixtures, so this test fails loudly if source
-- windows ever drift apart.

select
    s.session_id,
    s.session_started_at
from {{ ref('int_sessions_enriched_fx') }} as s
where not exists (
    select 1
    from {{ ref('stg_smard_prices') }} as p
    where p.market_zone = 'DE-LU'
        and p.timestamp_utc <= s.session_started_at
        and s.session_started_at < {{ dbt.dateadd('minute', 15, 'p.timestamp_utc') }}
)
