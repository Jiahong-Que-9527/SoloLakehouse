# Design: E04 · Incremental models, backfill and SCD Type 2

**E04 · Design specification (planned).** [Brief](../README.md) · [Implementation plan](implementation.md)

Convert `fct_charging_sessions` to an idempotent incremental `merge` model with a 48-hour lookback window and parameterized date-range backfill, implement `dbt snapshot` SCD Type 2 dimensions (`dim_stations_scd2`, `dim_tariffs_scd2`), and join sessions point-in-time so historical revenues never shift retroactively.

## 1. Decisions

| Topic | Decision |
|---|---|
| Incremental strategy | `materialized='incremental'`, `incremental_strategy='merge'`, `unique_key='session_id'`; merge source is `int_sessions_latest` (one recomputed row per session — contract §3.5). The stored row is replaced **wholesale**; per-event upserts of `event_seq` rows are forbidden (raw grain is `(session_id, event_seq)`, mart grain is `(session_id)`, so a late `event_seq=2` must trigger re-aggregation of that session, never a second fact row) |
| Late-arrival lookback | Default 48-hour lookback window (`settled_at >= max(settled_at) - 2 days`) |
| Bounded backfill | `--vars '{"backfill_start": "YYYY-MM-DD", "backfill_end": "YYYY-MM-DD"}'` overrides watermark filter |
| SCD Type 2 engine | `dbt snapshot` (`strategy='check'`) on `raw_stations_bnetza` and `raw_tariff_plans` per [ADR-0002](../../docs/adr/ADR-0002-scd2-via-dbt-snapshot.md) |
| Tracked SCD2 columns | Stations: `nominal_power_kw`, `connector_count`, `operator_name`; Tariffs: `price_per_kwh_eur`, `roaming_surcharge_eur`, `plan_tier` (see ADR-0002) |
| Point-in-time join | `session_started_at >= dbt_valid_from AND (session_started_at < dbt_valid_to OR dbt_valid_to IS NULL)` |

## 2. Scope boundary

In scope: `snapshots/` SCD2 models, incremental `fct_charging_sessions`, backfill CLI/vars support, full-refresh vs incremental row-parity test, and point-in-time historical tariff validation.

Out of scope: Slim CI (`E05`), BigQuery partitioning (`E06`), and Airflow backfill triggers (`E07`).

## 3. Architecture

```text
raw_stations_bnetza (t0, t1, t2) --[dbt snapshot]--> dim_stations_scd2 (dbt_valid_from/to)
raw_tariff_plans    (t0, t1, t2) --[dbt snapshot]--> dim_tariffs_scd2  (dbt_valid_from/to)
                                                            |
raw_charging_sessions (late 48h batch)                      | point-in-time interval join
        |  reduce to one row per session                    v
        '---[int_sessions_latest]--[incremental MERGE on session_id]---> fct_charging_sessions
```

## 4. Contracts and configuration

- `fct_charging_sessions` preserves its E03 `contract: {enforced: true}` schema while replacing `station_id`/`tariff_id` static joins with `station_sk`/`tariff_sk` from `dim_*_scd2`.
- Backfill vars default to `none` so normal scheduled runs use the 48-hour lookback watermark.

## 5. Behaviour and edge cases

1. Ingesting a late settlement arriving 36 hours after `session_started_at` updates its existing `session_id` cleanly without creating a second row: the merge recomputes the session's single row from all its raw events (golden example §4 Event 2 — the `event_seq=1` row is replaced by the corrected aggregate), matching [data-contract.md §3.5](../../docs/data-contract.md).
2. Re-running the exact same incremental window leaves row counts and totals identical.
3. Upgrading a station from 50 kW to 150 kW at `t1` closes the `50 kW` SCD2 record (`dbt_valid_to = t1`) and opens the `150 kW` record; sessions before `t1` stay joined to `50 kW`.
4. Running a bounded backfill (`backfill_start`..`backfill_end`) updates only dates in range and leaves surrounding dates untouched.

## 6. Delivery and cost

Offline DuckDB execution (`€0`). Cross-db date math uses `dbt.dateadd` so `E06` BigQuery runs without edits.

## 7. Acceptance criteria

1. Incremental build after late-arrival injection + backfill matches `dbt build --full-refresh` identically (row count + per-session hash).
2. `dim_stations_scd2` and `dim_tariffs_scd2` show non-overlapping `[dbt_valid_from, dbt_valid_to)` intervals per business key.
3. Historical session revenue stays unchanged after newer `t1`/`t2` tariff snapshots land.

## 8. Handoff

`E05` wraps the incremental watermark and cross-db helpers into reusable macros and wires Slim CI; `E06` enables BigQuery partitioning/clustering on `fct_charging_sessions`.
