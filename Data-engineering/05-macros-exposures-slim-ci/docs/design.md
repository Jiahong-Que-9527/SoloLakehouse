# Design: E05 · Macros, exposures and Slim CI

**E05 · Design specification (planned).** [Brief](../README.md) · [Implementation plan](implementation.md)

Standardize reusable cross-database Jinja macros (`dbt_utils` + project helpers), declare downstream BI and ML consumers in `exposures.yml`, generate complete `dbt docs` lineage, and implement state-aware **Slim CI** (`dbt build --select state:modified+ --defer`) in GitHub Actions.

## 1. Decisions

| Topic | Decision |
|---|---|
| Shared packages | `dbt-labs/dbt_utils` pinned in `dbt_project/packages.yml` (`dbt deps` locked) |
| Custom macros | `safe_divide`, `eur_currency_convert`, `incremental_lookback_filter`, `target_partition_config` |
| Downstream lineage | `dbt_project/models/exposures.yml` declaring `charging_revenue_dashboard` and `ev_demand_ml_features` |
| Docs verification | `dbt docs generate --static` + Python check verifying every mart column is documented |
| Slim CI strategy | Store baseline `manifest.json` from `main` CI artifact/cache; PR runs `dbt build --select state:modified+ --defer --state <prod_state>` |

## 2. Scope boundary

In scope: `packages.yml`, custom Jinja macros, `exposures.yml`, `dbt docs` completeness check, and Slim CI subgraph execution in GitHub Actions.

Out of scope: BigQuery live deployment (`E06`), Airflow scheduling (`E07`), and `run_results.json` telemetry parser (`E08`).

## 3. Architecture

```text
PR changes 1 mart model (or 1 staging model)
        |
        v
[Download baseline manifest.json from main]
        |
        v
dbt build --select state:modified+ --defer --state prod_state/
        |-- downstream-only edit -> builds only changed mart + its tests
        '-- upstream staging edit -> fans out to impacted downstream marts + tests
```

## 4. Contracts and configuration

- `target_partition_config(field, data_type, cluster_fields)` emits `partition_by` + `cluster_by` when `target.type == 'bigquery'` and stays a no-op on `duckdb`, keeping SQL 100% unified.
- `exposures.yml` links explicitly to `ref('fct_daily_revenue', v=2)` and `ref('fct_charging_sessions')` with owners and maturity tags.

## 5. Behaviour and edge cases

1. Editing only `fct_daily_revenue_v2.sql` triggers Slim CI to skip `staging` and `dim_*` builds by deferring to baseline state, running only the modified model and its tests.
2. Editing `stg_charging_sessions.sql` triggers `state:modified+` to rebuild the full impacted downstream path (`int_* -> fct_charging_sessions -> fct_daily_revenue`).
3. If no baseline `manifest.json` exists yet (e.g., first bootstrap run), CI falls back cleanly to a full `dbt build`.

## 6. Delivery and cost

`dbt deps`, `dbt docs generate`, and Slim CI run on `dbt-duckdb` in GitHub Actions (`€0`), cutting PR CI model execution work dramatically as the project grows.

## 7. Acceptance criteria

1. `dbt docs generate` renders full source-to-exposure lineage with 100% documented mart columns.
2. Slim CI verification proves both selective downstream execution and upstream fan-out with model counts and elapsed times recorded.
3. Cross-db macros compile cleanly under both `duckdb` and `bigquery` SQL compilation (`dbt compile --target bq`).

## 8. Handoff

`E06` uses the `target_partition_config` macro directly to materialize partitioned and clustered tables in live BigQuery.
