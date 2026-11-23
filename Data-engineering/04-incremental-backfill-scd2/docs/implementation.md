# Implementation plan: E04 · Incremental models, backfill and SCD Type 2

**Status:** planned. [Brief](../README.md) · [Design](design.md) · [Delivery plan](../../docs/delivery-plan.md)

## First delivery

Implement `dbt snapshot` SCD Type 2 dimensions for stations and tariffs across `t0/t1/t2` snapshots, convert `fct_charging_sessions` to incremental `merge` with a 48-hour lookback and parameterized backfill, and prove exact parity with `--full-refresh`.

## Files and modules to create or update

- `Data-engineering/reference-warehouse/dbt_project/snapshots/dim_stations_scd2.sql`
- `Data-engineering/reference-warehouse/dbt_project/snapshots/dim_tariffs_scd2.sql`
- `Data-engineering/reference-warehouse/dbt_project/snapshots/schema.yml`
- `Data-engineering/reference-warehouse/dbt_project/models/marts/fct_charging_sessions.sql` (incremental merge + point-in-time SCD2 join)
- `Data-engineering/reference-warehouse/dbt_project/models/marts/schema.yml` (update foreign-key/surrogate-key tests)
- `Data-engineering/reference-warehouse/tests/test_incremental_scd2.py`
- `Data-engineering/04-incremental-backfill-scd2/evidence/e04-acceptance.md`

## Implementation sequence

1. **SCD Type 2 snapshots:** Create `snapshots/dim_stations_scd2.sql` and `snapshots/dim_tariffs_scd2.sql` using `strategy='check'` and `updated_at='snapshot_date'` (or `check_cols`), plus tests verifying zero overlapping validity windows per natural key.
2. **Incremental `fct_charging_sessions`:** Configure `materialized='incremental'`, `incremental_strategy='merge'`, `unique_key='session_id'`, 48h `dbt.dateadd` lookback filter, and `var('backfill_start', none)` / `var('backfill_end', none)` override.
3. **Point-in-time joins:** Join `fct_charging_sessions` to `dim_stations_scd2` and `dim_tariffs_scd2` on `[dbt_valid_from, dbt_valid_to)` at `session_started_at`, and update `fct_daily_revenue` downstream.
4. **Full-refresh parity test (`test_incremental_scd2.py`):** Run `t0` -> snapshot -> build -> ingest `t1` + late settlements -> snapshot -> incremental build; clone/compare all rows against a clean `--full-refresh` DuckDB run.
5. **Record evidence:** Document late-arrival updates, SCD2 interval history for an upgraded station/tariff, and exact parity results in `evidence/e04-acceptance.md`.

## Verification commands and negative drills

```bash
cd Data-engineering/reference-warehouse
uv run --locked sqlfluff lint dbt_project/models dbt_project/snapshots
uv run --locked dbt snapshot --project-dir dbt_project --profiles-dir dbt_project --target duckdb
uv run --locked dbt build --project-dir dbt_project --profiles-dir dbt_project --target duckdb
uv run --locked pytest tests/test_incremental_scd2.py -v
```

**Negative / edge drill:** Re-run incremental build on the same `t1` batch twice and verify row count, surrogate keys, and revenue totals remain unchanged; confirm `t0` session tariff prices did not change after `t1` tariff hike.

## Acceptance evidence

Record in `04-incremental-backfill-scd2/evidence/e04-acceptance.md`: incremental vs `--full-refresh` diff count (`0`), SCD2 before/after rows for one upgraded station & one repriced tariff, and bounded backfill `--vars` run log.
