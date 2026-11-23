# E02 acceptance evidence · Dimensional modeling with dbt

**Run date (UTC):** 2026-11-23 · **Branch:** `feat/e02-dbt-dimensional-modeling` (base: latest `origin/main` incl. PR #281 contract v1.3 + PR #287 progress checkpoint) · **Outcome: PASS**

## Environment

| Item | Value |
|---|---|
| Python (project venv) | 3.12.13 (`requires-python = ">=3.12,<3.13"`) |
| dbt-core | 1.12.7 |
| dbt-duckdb | 1.11.1 |
| dbt-bigquery | 1.12.4 (adapter pinned per delivery-plan E02 decision; `bq` target lands in E06) |
| sqlfluff / templater-dbt | 4.5.0 / 4.5.0 |
| duckdb | 2.0.1 |
| `uv.lock` SHA-256 | `ed283998d2f65bad`… (locked with all four tools above) |
| dbt artifact schema | `run_results/v6.json` |

## What landed

- `dbt_project/` with **14 models** (6 `stg_*` views, 3 `int_*` views, 5 mart tables), **75 data tests** (all passing), `sources.yml` with freshness SLAs (warn 24h / error 48h), and cross-warehouse macros (`cross_db.sql`): `to_berlin_date`, `iso_day_of_week`, `date_spine`, `safe_divide`, `generate_schema_name` — contract §3.9: no per-adapter SQL forks; the only dialect branches live inside macros.
- Modeling follows **contract v1.3**: `stg_charging_sessions` is 1:1 with raw minus byte-identical duplicates (`unique(session_id, event_seq)`); `int_sessions_latest` owns the latest-event reduction (`unique(session_id)`, ties by `_ingested_at` then `_source_hash`); `fct_charging_sessions` reads only from it; `revenue_date` is the `Europe/Berlin` civil date; FX is ECB-base carry-forward with `observed`/`carried_forward`; SMARD slot pricing per §3.8 with the deterministic boundary fallback.
- Money columns are `cast(round(x / rate, 2) as decimal(18, 2))` — DuckDB (like BigQuery) returns DOUBLE for DECIMAL division, and the cast makes every EUR column exact 2-decimal money (§3.3), verified cent-exact below.
- `.sqlfluff` (sqlfluff 4.5): `LT12, ST06, ST09, AM04` excluded with rationale in the file (ST09's default contradicts AM05's joined-table-first ON clauses; `select s.*` pass-throughs are idiomatic in staging/intermediate).
- `tests/test_dbt_models.py`: the full offline loop per session fixture — generate → ingest (all 6 sources incl. the in-process mock roaming API) → `dbt source freshness` → `dbt build --target duckdb` — followed by fixture-exact assertions (FX carry-forward for every roaming row, SMARD slot price + cost for every session, DST revenue attribution, dim_date calendar, zero fan-out, fact↔daily cent-exact reconciliation).
- `.github/workflows/data-engineering.yml`: path-scoped (`Data-engineering/reference-warehouse/**`), fully offline (fixtures only, no GCP credentials).

## Commands (after final edit)

```bash
uv sync --locked --python 3.12
uv run --locked ruff check .            # All checks passed!
uv run --locked ruff format --check .   # clean
uv run --locked sqlfluff lint dbt_project/models   # All Finished! (0 violations)
uv run --locked pytest -q               # 20 passed (13 E01 + 7 E02) in ~30s
```

## dbt source freshness (6 of 7 sources; `raw_quarantine` opted out — no `_ingested_at` column)

All sources `PASS` immediately after ingestion. Empty-by-design sources are impossible here: the harness ingests all six sources, so no STALE false positives.

## dbt build + fan-out verification (fresh disposable warehouse)

```
raw raw_charging_sessions   12,728 events (12,000 valid sessions after 40 quarantined rows + E04-relevant event_seq=2 rows and duplicates)
raw raw_roaming_settlements  3,599 valid (4 fault rows quarantined)
raw.raw_quarantine              44 rows: negative_energy_kwh 25 · invalid_timestamp_order 15 ·
                                invalid_type 1 · missing_required_column 1 · null_primary_key 1 · unexpected_schema_drift 1
int.int_sessions_latest     12,000 rows
mart.fct_charging_sessions  12,000 rows   ← count(distinct session_id) == int == fct  (zero fan-out)
mart.fct_daily_revenue       7,662 rows
sum(net_amount_eur) fact    = 414,336.68   ==  sum(net_amount_eur) daily  (DECIMAL-exact, Δ 0.00)
```

`dbt build` result: `PASS=60 ERROR=0` (14 models + 75 tests within 90 nodes), ~3.3 s model+test elapsed.

## Negative drills

| Drill | Observed |
|---|---|
| Stale source (>48h) | `update raw.raw_ecb_fx_rates set _ingested_at = now() - interval 72 hours` → `dbt source freshness` exits **non-zero** with `ERROR STALE` (`test_stale_source_fails_freshness`) |
| Misformatted/unqualified SQL | Injected `zz_lint_drill.sql` into `models/staging/` with unqualified references and a bare `on 1 = 1` join → `sqlfluff lint` exits **1** (RF02 ×3, AM05); removed → lint green again |
| Quarantine-orphan settlements | 4 roaming settlements reference sessions whose charge events were quarantined; the session-driven fact build excludes them (no FK test on `stg_roaming_settlements.session_id` — semantics documented in `schema.yml`) |

## Decisions recorded

1. **`is_de_holiday` source:** frozen list of German nationwide + Hessen holidays for 2025-10-01..2026-05-31 inside `dim_date.sql` (Oct 3, Dec 25/26, Jan 1, Karfreitag, Ostermontag, May 1, Christi Himmelfahrt, Pfingstmontag). ECB calendar covers only TARGET2; per-state holiday feeds are outside offline-CI scope.
2. **dbt 1.12 test syntax:** `data_tests:` + `arguments:` blocks (the legacy `tests:` + bare kwargs form fails dbt 1.12.7 with `MissingArgumentsPropertyInGenericTestDeprecation` treated as an error).
3. **dbt-bigquery pinned now** (delivery-plan E02 decision) although the `bq` target is only configured in E06.
4. **Schema naming:** exact `stg`/`int`/`mart` schemas via `generate_schema_name` macro (no `main_` prefixing).

## Skipped checks and why

- BigQuery/`--target bq` checks: E06 scope. CI runs GitHub Actions with zero cloud credentials.
- Live refresh (`--live`): operator action, fixtures locked (unchanged from E01).

## CI

GitHub Actions run for this PR: see the `data-engineering` workflow on the merge PR (path-scoped; same commands as above).
