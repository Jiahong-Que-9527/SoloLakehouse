-- Singular test: the mart's natural grain (event_date, region) must be
-- unique. Singular tests like this one are the dependency-free way to pin a
-- composite grain (the primary warehouse uses dbt_utils's
-- unique_combination_of_columns once a packages.yml exists).

select
    event_date,
    region,
    count(*) as rows_on_grain
from {{ ref('fct_example_summary') }}
group by event_date, region
having count(*) > 1
