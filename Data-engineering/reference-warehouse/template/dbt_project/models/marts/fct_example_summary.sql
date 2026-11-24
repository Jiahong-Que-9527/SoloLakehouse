-- Mart: daily grain with an enforced contract (see schema.yml). This whole-
-- row aggregate shape is the E03/E05 convention: describe every column,
-- declare data_type + not_null constraints, test the grain.

select
    event_date,
    region,
    count(*) as event_count,
    cast(sum(amount_eur) as decimal(18, 2)) as total_amount_eur
from {{ ref('stg_example_events') }}
group by event_date, region
