# E03 acceptance evidence · Testing, data contracts and versioning

**Run date (UTC):** 2026-11-23 · **Branch:** `feat/e03-testing-contracts-versioning` (base: latest `origin/main` incl. E02 @ PR #290) · **Outcome: PASS**

## Environment

| Item | Value |
|---|---|
| Python (project venv) | 3.12.13 |
| dbt-core | 1.12.7 |
| dbt-duckdb | 1.11.1 |
| dbt-bigquery | 1.12.4 |
| sqlfluff / templater-dbt | 4.5.0 / 4.5.0 |
| duckdb | 2.0.1 |
| `uv.lock` SHA-256 | `ed283998d2f65bad`… (unchanged from E02 — no new Python dependencies) |
| Contract version | **v1.4** (see decisions) |

## What landed

- **Enforced contracts** (`contract: {enforced: true}` + explicit `data_type` + `not_null` constraints) on all five marts: `dim_date`, `dim_stations`, `dim_tariffs`, `fct_charging_sessions`, `fct_daily_revenue` (both versions). All passed **on the first build** — the E02 models already matched the contracted types, thanks to the explicit `decimal(18,2)` casts.
- **`fct_daily_revenue` versioning:** `latest_version: 2`; `v1` (`fct_daily_revenue_v1.sql`, `deprecation_date: 2027-02-28`) and `v2` (`fct_daily_revenue_v2.sql`, adds `wholesale_cost_eur` + `gross_margin_eur`) both build as separate relations. Non-breaking additive change, pre-resolved by contract v1.1.
- **Custom generic tests** (`dbt_project/tests/generic/`): `non_negative` (energy is a physical measurement, never negative — contract §1.4) and `non_negative_unless_refund` (signed money columns). Applied to staging energy and fct money columns.
- **Singular tests** (`dbt_project/tests/singular/`): `assert_revenue_conservation.sql` in the canonical §3.1 form (independent recomputation from `int_sessions_latest` + `stg_ecb_fx` + `stg_roaming_settlements`, quarantined rows excluded, tolerance 0.00 EUR) and `assert_no_session_outside_price_window.sql` (the §3.8 boundary fallback must never fire).
- **6 native `unit_tests`** with inline mock rows, including the **binding golden example** (contract §4):
  `int_sessions_latest_reduces_to_highest_event_seq`, `int_sessions_latest_tie_break_by_ingested_at`, `int_sessions_enriched_fx_dst_revenue_date` (2025-10-25 23:30 UTC → 2025-10-26 Berlin), `int_sessions_enriched_fx_carries_forward_over_weekend` (Sunday carries Friday's rate, never Monday's), `int_sessions_wholesale_cost_golden_charge` (Event 1: 45.2 kWh × 95 EUR/MWh → 4.29), `fct_charging_sessions_golden_refund_signs` (Event 3: gross −26.66, roaming −1.50, net −28.16, wholesale −4.29, margin −23.87).
- `tests/conftest.py`: shared warehouse fixture + helpers (E02/E03 tests now share one offline loop); `tests/test_contracts.py`: automated negative drills.

## Commands (after final edit)

```bash
uv sync --locked --python 3.12
uv run --locked ruff check .                                   # All checks passed!
uv run --locked ruff format --check .                          # clean
uv run --locked sqlfluff lint dbt_project/models dbt_project/tests   # All Finished!
uv run --locked pytest -q                                      # 25 passed (13 E01 + 7 E02 + 5 E03)
```

## dbt build (fresh disposable warehouse)

```
Found 15 models, 88 data tests, 7 sources, 519 macros, 6 unit tests
Done. PASS=109 WARN=0 ERROR=0 SKIP=0   (models 15 · data tests 88 · unit tests 6, ~3.9 s)
```

Test counts by category: 88 data tests = built-in generics (`not_null`/`unique`/`relationships`/`accepted_values`) + 2 custom generics (applied to 6 columns) + 2 singular; 6 unit tests. All passing.

## Negative drills (automated in `tests/test_contracts.py`)

| Drill | Observed |
|---|---|
| Contract breach (retype `gross_amount_eur` to `DECIMAL(18,3)` in a project copy) | `dbt build` exits **1**: `This model has an enforced contract that failed … \| gross_amount_eur \| DECIMAL(18,3) \| DECIMAL(18,2) \| data type mismatch \|`; the previous valid table is preserved (type verified `DECIMAL(18,2)` after the failed build) |
| 0.01 EUR conservation drift | `update mart.fct_charging_sessions set net_amount_eur += 0.01` → `dbt test --select assert_revenue_conservation` exits **non-zero** |
| Golden example regression | Covered by `unit_tests` in every build (mock rows are the §4 inputs, expected rows are the §4 outputs) |

## Decisions recorded

1. **Contract v1.4 — negative-price wholesale sign (test run caught it):** the locked SMARD fixture contains real negative DE-LU slot prices, so `charge` rows can legitimately carry **negative** `wholesale_cost_eur` (361 charges + 8 late-adjustments in negative-price hours were flagged by the first `non_negative_unless_refund` run). Contract §2 reworded: charge/late-adjustment keep the slot price's own sign; refund inverts it. The generic test was removed from `wholesale_cost_eur` only (kept on gross/roaming/net); wholesale sign consistency remains covered by the golden `unit_tests` and the fixture-exact pytest recompute. Changelog entry in the contract.
2. **Contract v1.2/v1.3 wording tension resolved:** golden-example `unit_tests` use inline mock rows (the §4 inputs/outputs), independent of the locked open-data fixtures — end-to-end runs recompute the same formulas against real locked rates (validated separately by pytest).
3. **dbt 1.12 `data_tests:`/`arguments:` syntax** for all new YAML (E02 baseline).
4. **Orphan settlements:** no FK test on `stg_roaming_settlements.session_id` (source may reference quarantined sessions; fact build is session-driven) — carried over from E02, documented in `schema.yml`.

## Skipped checks and why

- BigQuery/`--target bq`: E06 scope.
- `dbt build --full-refresh` parity: E04 acceptance (incremental models land there).

## CI

GitHub Actions run for this PR: see the `data-engineering` workflow on the merge PR (lint now also covers `dbt_project/tests`).
