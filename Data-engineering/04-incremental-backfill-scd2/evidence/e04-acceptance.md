# E04 acceptance evidence · Incremental models, backfill and SCD Type 2

**Run date (UTC):** 2026-11-23 · **Branch:** `feat/e04-incremental-scd2` (base: latest `origin/main` incl. E03 @ PR #295) · **Outcome: PASS**

## Environment

| Item | Value |
|---|---|
| Python (project venv) | 3.12.13 |
| dbt-core | 1.12.7 · dbt-duckdb 1.11.1 · dbt-bigquery 1.12.4 |
| sqlfluff / templater-dbt | 4.5.0 / 4.5.0 |
| duckdb | 2.0.1 |
| `uv.lock` SHA-256 | `ed283998d2f65bad`… (unchanged — no new Python dependencies) |
| Contract version | **v1.5** (surrogate-key type change, see decisions) |

## What landed

- **`dbt snapshot` SCD2 dimensions** (`snapshots/dim_stations_scd2.sql`, `dim_tariffs_scd2.sql`, `strategy='timestamp'`, `unique_key=station_id/tariff_id`): the raw `t0/t1/t2` snapshot dates act as **simulated time** — `dbt_valid_from`/`dbt_valid_to` are raw snapshot dates, so point-in-time joins work for historical 2025–2026 sessions. `updated_at` = the earliest raw snapshot date at which the tracked attributes equal the as-of values (computed in the snapshot SELECT), making repeated runs idempotent.
- **`fct_charging_sessions` → incremental `merge`** (`unique_key='session_id'`, `on_schema_change='fail'`): 48-hour `dbt.dateadd` lookback against the stored watermark, overridable with `--vars '{"backfill_start": …, "backfill_end": …}'`; merge source is the recomputed `int_sessions_latest` row (whole-row replacement, per-event upserts forbidden — contract §3.5).
- **Point-in-time joins (§3.6):** the fact joins `dim_stations_scd2`/`dim_tariffs_scd2` on natural key + `[dbt_valid_from, dbt_valid_to)` at `session_started_at`; `station_sk`/`tariff_sk` are the snapshot surrogate ids (`dbt_scd_id`, `varchar` — contract v1.5). `dim_stations`/`dim_tariffs` are now views over the SCD2 tables (`dbt_valid_to is null`); `fct_daily_revenue` v1/v2 resolve `operator_name` point-in-time through `dim_stations_scd2`.
- **Guards:** `assert_scd2_no_overlapping_intervals.sql` (both entities, open-ended current version handled); snapshot tests (`unique dbt_scd_id`, `not_null` keys).
- **`tests/test_incremental_scd2.py`** (6 tests): interval history, point-in-time joins, incremental idempotence, late-settlement replacement, exact full-refresh parity, bounded backfill. `tests/conftest.py` now replays the snapshot sequence (t0 → t1 → t2) and builds models before the test-bearing `dbt build`.

## Commands (after final edit)

```bash
uv sync --locked --python 3.12
uv run --locked ruff check . && uv run --locked ruff format --check .   # clean
uv run --locked sqlfluff lint dbt_project/models dbt_project/tests      # clean (exit 0)
uv run --locked pytest -q                                               # 31 passed (13 E01 + 7 E02 + 5 E03 + 6 E04)
```

## SCD2 evidence (fresh warehouse, snapshot replay t0 → t1 → t2)

| Measure | Value |
|---|---|
| `dim_stations_scd2` rows | 3,597 (3,233 current + 364 historical versions) |
| Stations with >1 version | 362 (≈8% power upgrades + 2% operator changes, per generator fault plan) |
| `dim_tariffs_scd2` rows | 8 (6 tariffs; `T-DE-STD-01` and `T-ROAM-PL-01` repriced) |
| `dim_stations` / `dim_tariffs` (current views) | 3,233 / 6 |
| `fct_charging_sessions` | 12,000 (zero fan-out preserved) |
| `dbt_valid_from` domain | {2025-09-15, 2026-01-15, 2026-05-15} exactly |

**Upgraded station (before/after):** station `1017326` — version `[2025-09-15, 2026-01-15)` @ 92 kW, version `[2026-01-15, ∞)` @ 184 kW.

**Repriced tariff (before/after):** `T-DE-STD-01` — version `[2025-09-15, 2026-01-15)` @ 0.59 EUR/kWh, version `[2026-01-15, ∞)` @ 0.62 EUR/kWh.

**Point-in-time proof** (`test_point_in_time_station_join`): a session starting before 2026-01-15 at an upgraded station joins the 92 kW version; a session on/after 2026-01-15 joins the 184 kW version. Historical revenue never shifts.

## Incremental merge evidence

| Drill | Observed |
|---|---|
| Incremental re-run, no new data | count and `sum(net_amount_eur)` byte-identical before/after |
| Late settlement (`event_seq=2`, settled now) | merge replaces the session row **wholesale**: count unchanged, `event_type` → `late_adjustment`, `settled_at` → the late event's |
| Incremental vs `--full-refresh` | `EXCEPT ALL` both directions → **0 rows diff** |
| Bounded backfill (`backfill_start=2025-01-01, backfill_end=2025-11-01`) | after deleting all rows with `settled_at < 2025-11-01`, the bounded run restores count and revenue exactly |

## Commands for the negative/edge drills

```bash
dbt run --select fct_charging_sessions                                   # idempotence
dbt run --select fct_charging_sessions --vars '{"backfill_start": "2025-01-01", "backfill_end": "2025-11-01"}'
dbt run --full-refresh --select fct_charging_sessions                    # parity reference
```

(All wired as pytest tests; the drills run against disposable copies of the warehouse.)

## Decisions recorded

1. **`strategy='timestamp'` with simulated time, not `check`:** with `check`, `dbt_valid_from` would be the wall-clock run time, and historical 2025–2026 sessions would find no valid dimension row. The raw `snapshot_date` provides the time axis; `updated_at` is derived in the snapshot SELECT as the earliest snapshot date at which the current attributes hold — idempotent across runs (the first implementation propagated the change date only one step back and churned every station; the test run caught it — 6,468 rows instead of 3,597).
2. **Contract v1.5:** `station_sk`/`tariff_sk` retyped `bigint` → `varchar` (`dbt_scd_id`) across `dim_stations`, `dim_tariffs`, `fct_charging_sessions` — version-level surrogate keys. The v1.3 build-order note's "no contract change at E04" claim was wrong about types; corrected in the contract's build-order note + changelog.
3. **`on_schema_change='fail'`:** dbt 1.12 requires it for incremental models with enforced contracts; `fail` is the safe default for a locked schema.
4. **dbt 1.12 unit-test overrides:** incremental models' unit tests need `overrides: {macros: {is_incremental: true}}` + a `this` input mock (the golden refund test now exercises the incremental path with a mocked watermark row).
5. **sqlfluff scope:** `dbt_project/snapshots` is excluded from lint — sqlfluff 4.5 reports 48 unfixable layout violations on `{% snapshot %}`-wrapped files (rendering artifact). Snapshot correctness is covered by the 6 E04 tests + the interval guard.

## Skipped checks and why

- BigQuery/`--target bq`: E06.
- Snapshot behavior on hard deletes: `invalidate_hard_deletes=False` — raw snapshots are append-only by design (E01), so no deletes occur.

## CI

GitHub Actions run for this PR: see the `data-engineering` workflow on the merge PR.
