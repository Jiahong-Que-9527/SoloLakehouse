# E05 acceptance evidence · Macros, exposures and Slim CI

**Run date (UTC):** 2026-11-24 · **Branch:** `feat/e05-macros-exposures-slim-ci` (base: latest `origin/main` incl. E04 @ PR #309) · **Outcome: PASS**

## Environment

| Item | Value |
|---|---|
| Python (project venv) | 3.12.13 |
| dbt-core | 1.12.7 · dbt-duckdb 1.11.1 · dbt-bigquery 1.12.4 |
| dbt_utils | 1.4.1 (`packages.yml`, `package-lock.yml` SHA-256 `a4d6f0312e87bc54`…) |
| sqlfluff / templater-dbt | 4.5.0 / 4.5.0 |
| duckdb | 2.0.1 |
| Contract version | v1.5 (unchanged in this stage) |

## What landed

- **`dbt_project/packages.yml` + `package-lock.yml`:** `dbt-labs/dbt_utils` pinned; `dbt deps` locked and wired into CI + the test fixture.
- **`macros/cross_db_helpers.sql`:** `eur_currency_convert` (single division, half-up, exact `DECIMAL(18,2)` — §3.3), `incremental_lookback_filter` (48h watermark + bounded backfill override, contract §3.5; watermark aggregate uses the bare column name — a table-qualified aggregate breaks under dbt unit-test rendering, caught by the golden `unit_test`), `target_partition_config(field, data_type, cluster_fields)` (emits `partition_by`/`cluster_by`/`require_partition_filter` on BigQuery, no-op elsewhere — §3.9). `fct_charging_sessions` refactored to call all three; `safe_divide` remains in `cross_db.sql`.
- **`exposures.yml`:** `charging_revenue_dashboard` (dashboard, depends on `ref('fct_daily_revenue', v=2)`) and `ev_demand_ml_features` (ml, depends on `ref('fct_charging_sessions')`), with owners and maturity.
- **100% mart column documentation:** all 57 mart columns (incl. both `fct_daily_revenue` versions) carry non-empty descriptions; verified against `manifest.json` by `test_mart_columns_fully_documented`, with a negative drill (`test_doc_coverage_check_catches_missing_description`). Composite `unique` tests refactored to `dbt_utils.unique_combination_of_columns` (staging ×3, `fct_daily_revenue` v1/v2).
- **Slim CI (design §5):** CI uploads `target/manifest.json` as the `prod-state` artifact on `main` pushes; PRs download the last successful `main` artifact and run the slim-ci tests against it; no artifact → clean full-build fallback (design §5.3). Locally, `tests/test_slim_ci.py` simulates the flow with a baseline manifest + project copies.
- **`dbt compile --target bq`:** exits **0** with the new macros (offline SQL compilation under the BigQuery adapter; see decisions).

## Commands (after final edit)

```bash
uv sync --locked --python 3.12
uv run --locked dbt deps --project-dir dbt_project --profiles-dir dbt_project
uv run --locked ruff check . && uv run --locked ruff format --check .           # clean
uv run --locked sqlfluff lint dbt_project/models dbt_project/tests              # clean (exit 0)
uv run --locked pytest -q                                                       # 36 passed
```

## Slim CI selection & runtime evidence (`tests/test_slim_ci.py`)

| Scenario | Selected models | Full-build comparison |
|---|---|---|
| Edit leaf mart `fct_daily_revenue_v2.sql` | exactly `fct_daily_revenue.v2` (1 model) | 15 models |
| Edit upstream `stg_ecb_fx.sql` | `stg_ecb_fx` + `int_sessions_enriched_fx` + `int_sessions_wholesale_cost` + `fct_charging_sessions` + `fct_daily_revenue.v1` + `.v2` (6 models) | 15 models |
| Fresh-env slim build (`dbt build --select +state:modified+ --defer --state`) | executes exactly the 6 impacted models + their tests, `rc=0` | 15 models + 88 data tests + 6 unit tests |

(Exact node sets asserted against `dbt ls --select state:modified+ --state`; the fresh-env build verifies the ephemeral-duckdb CI pattern where the `+` ancestor prefix materializes the upstream chain.)

## Doc coverage

`mart columns documented: 57/57 (100%)` — every column of `dim_date`, `dim_stations`, `dim_tariffs`, `fct_charging_sessions`, `fct_daily_revenue` v1+v2 has a non-empty description in `manifest.json`; exposures verified present. Negative drill: stripping one description yields exactly one gap.

## dbt compile --target bq

`dbt compile --target bq` exits **0** and renders BigQuery SQL with the new `target_partition_config` macro (partition on `revenue_date`, cluster by `country_code, station_sk`). Note: a *cold* parse (`target/` deleted) attempts a live BigQuery connection and fails without credentials (`Database Error`) — the compile-only proof relies on dbt's incremental parse, and the cold-parse + live deployment validation lands in E06 where credentials exist.

## Decisions recorded

1. **Slim CI on an ephemeral duckdb:** `--defer` is kept in the CI command per design, but on a throwaway database the deferral cannot resolve unselected refs — the ancestor prefix (`+state:modified+`) materializes the upstream chain so the modified subgraph can execute. Recorded as the project's ephemeral-warehouse Slim CI pattern; with a persistent warehouse, plain `state:modified+ --defer` applies directly.
2. **dbt 1.12 `overrides.macros.is_incremental`:** the golden refund unit test exercises the incremental path with a mocked `this` watermark row (dbt 1.12 requires the `macros` nesting and, for `is_incremental: true`, a `this` input).
3. **View-constraint warnings silenced:** `warn_unsupported: false` on the two view dims' `not_null` constraints (dbt ignores constraints on views); the source-level `freshness`/`loaded_at_field` properties moved into `config` (dbt 1.12 syntax), removing all `PropertyMovedToConfigDeprecation` warnings.
4. **Roaming skipped in the CI slim prep:** the workflow's slim path ingests the five file sources and skips the mock-API roaming batch (no in-process server in shell) — the empty `raw_roaming_settlements` builds cleanly and the slim job's purpose (selection + subgraph build) is unaffected. The full 6-source loop runs in the main CI job via pytest.

## Skipped checks and why

- Live BigQuery deployment/`bytes_billed`: E06.
- `dbt docs generate --static` site rendering: the manifest-level completeness check (this stage's criterion) covers documentation; the static site is verified in E08's observability work.

## CI

GitHub Actions run for this PR: see the `data-engineering` workflow on the merge PR (deps + slim-ci artifact flow active).
