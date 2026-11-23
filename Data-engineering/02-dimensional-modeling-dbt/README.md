# E02 · Dimensional modeling with dbt

**Status:** planned · [Roadmap](../README.md) · [Delivery plan](../docs/delivery-plan.md)

Establish the `dbt` project over the Raw layer using `dbt-duckdb`: source freshness definitions, clean `staging` (`stg_*`), reusable `intermediate` (`int_*`), and a Kimball star schema in `marts` (`fct_charging_sessions`, `fct_daily_revenue`, `dim_stations`, `dim_tariffs`, `dim_date`), enforced by SQLFluff and path-scoped GitHub Actions CI.

## Deliverables

- `dbt_project/` configured with `dbt-duckdb` target, `sources.yml` (including `loaded_at_field` and freshness thresholds), and layered directories (`staging/`, `intermediate/`, `marts/`).
- Star-schema models with documented grains, EUR currency normalization (safe ECB holiday carry-forward), and zero fan-out across dimension joins.
- `.sqlfluff` configuration + `.github/workflows/data-engineering.yml` running `ruff`, `pytest`, `sqlfluff lint`, and `dbt build` offline on DuckDB.

## Acceptance

1. `dbt source freshness` and `dbt build` succeed cleanly on the E01 Raw fixture in < 15 seconds on DuckDB.
2. Join fan-out check confirms `COUNT(fct_charging_sessions) == COUNT(distinct session_id)` with zero duplicated revenue.
3. `sqlfluff lint` and GitHub Actions CI pass with zero warnings on clean SQL models and fail visibly on an intentionally broken model.
