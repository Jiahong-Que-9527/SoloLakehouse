# Design: E02 · Dimensional modeling with dbt

**E02 · Design specification (planned).** [Brief](../README.md) · [Implementation plan](implementation.md)

<!-- [ZCode·2026-11-23] Align mart naming with data-contract v1.1 (current-state dims as views; SCD2 in E04), bind dedup and revenue_date rules to the contract, and note freshness SLAs are injection-verified locally. -->

Establish the `dbt-core` + `dbt-duckdb` project over E01 Raw tables: source definitions with freshness SLAs, `staging` (`stg_*`), `intermediate` (`int_*`), and Kimball star-schema `marts` (`fct_charging_sessions`, `fct_daily_revenue`, `dim_stations`, `dim_tariffs`, `dim_date`), enforced by SQLFluff and path-scoped GitHub Actions CI.

## 1. Decisions

| Topic | Decision |
|---|---|
| Adapter & version | `dbt-core` + `dbt-duckdb` + `dbt-bigquery` pinned in `uv.lock` (Python 3.12) |
| Schema layers | `raw` (E01) -> `stg` (views) -> `int` (ephemeral/views) -> `mart` (tables) |
| SQL dialect & linting | `.sqlfluff` (`templater = dbt`, `dialect = duckdb` locally; cross-db SQL verified against BigQuery rules) |
| Currency normalization | Convert `CHF`/`PLN` to `EUR` using latest ECB rate `<= revenue_date` in ECB base notation (`EUR/CHF`, `rate` = foreign units per `1 EUR`); tag `fx_rate_status` (`observed` / `carried_forward`) per [data-contract.md §1.3](../../docs/data-contract.md) |
| Revenue attribution | `revenue_date` = `Europe/Berlin` civil date of `session_started_at` (contract §3.4); all other timestamps stay UTC |
| CI workflow | `.github/workflows/data-engineering.yml` path-scoped to `Data-engineering/reference-warehouse/**` |

## 2. Scope boundary

In scope: `dbt_project.yml`, `profiles.yml` (`duckdb` target), `sources.yml` with freshness, `stg_*` / `int_*` / `mart` models, SQLFluff config, pytest dbt smoke harness, and GitHub Actions CI.

Out of scope: native dbt `unit_tests` & enforced `contract` (`E03`), incremental `merge` & `dbt snapshot` (`E04`), `Slim CI` (`E05`), and live BigQuery target (`E06`).

## 3. Architecture

```text
raw.* (E01 DuckDB)
   |
   +--> staging (views): stg_bnetza_stations, stg_smard_prices, stg_ecb_fx,
   |                     stg_charging_sessions, stg_roaming_settlements, stg_tariff_plans
   +--> intermediate (views): int_sessions_enriched_fx, int_sessions_wholesale_cost
   +--> marts (tables): dim_date, fct_charging_sessions, fct_daily_revenue
   +--> marts (E04, after snapshots land): dim_stations_scd2 / dim_tariffs_scd2 (snapshots)
                                           dim_stations / dim_tariffs (current-state views, contract §2)
```

Until `E04`, `dim_stations` / `dim_tariffs` build directly from the latest `raw` snapshot (`t0/t1/t2`); from `E04` they become views over the SCD2 tables per [data-contract.md §2](../../docs/data-contract.md).

## 4. Contracts and configuration

- `sources.yml` declares `loaded_at_field: _ingested_at` and `freshness: {warn_after: {count: 24, period: hour}, error_after: {count: 48, period: hour}}`.
- `fct_charging_sessions` grain is strictly 1 row per `session_id`; `fct_daily_revenue` grain is `(revenue_date, country_code, operator_name)`.
- Staging dedup follows the contract rule (§3.2): one row per `session_id` by `max(event_seq)`, ties by `_ingested_at` then `_source_hash`.
- `dbt_project.yml` enables `persist_docs: {relation: true, columns: true}` and clean schema naming.

## 5. Behaviour and edge cases

1. Duplicate `session_id` events in `raw_charging_sessions` reduce deterministically to the latest `event_seq` in `stg_charging_sessions` before joining dimensions (preventing fan-out); the binding rule lives in [data-contract.md §3.2](../../docs/data-contract.md).
2. Sessions on weekends or TARGET2 holidays find the most recent ECB rate on or before `revenue_date` without lookahead.
3. Missing upstream source data triggers `dbt source freshness` failure visibly. On the local/offline track the 24h/48h SLAs are exercised by injected timestamps (E01 generator and the E08 drill), not by wall-clock waiting.

## 6. Delivery and cost

Offline execution on `dbt-duckdb` takes `< 15s` in CI (`€0`). No GCP credentials or network access are used in PR checks.

## 7. Acceptance criteria

1. `dbt source freshness` and `dbt build --target duckdb` pass cleanly on E01 Raw outputs.
2. Row-count and grain checks prove zero fan-out (`COUNT(*) == COUNT(DISTINCT session_id)`).
3. `sqlfluff lint` passes cleanly on valid models and fails on an intentionally misformatted SQL model in CI/drill verification.

## 8. Handoff

`E03` adds enforced `contract`, model versions, native `unit_tests`, and singular revenue-conservation tests directly onto these models.
