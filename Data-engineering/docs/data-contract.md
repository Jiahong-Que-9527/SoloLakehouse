# Data contract and dimensional model specification

<!-- [Antigravity·2026-11-23] Initialize source contracts, star-schema grains, and invariants. -->

## 1. Raw source tables

Every ingested raw table carries standard lineage metadata: `_batch_id`, `_ingested_at`, `_source_name`, `_source_hash`.

| Source table | Origin | Grain | Notes |
|---|---|---|---|
| `raw_stations_bnetza` | Bundesnetzagentur Ladesäulenregister (`CC BY 4.0`) + `t0/t1/t2` snapshots | `(station_id, snapshot_date)` | Real German public charging stations (locked regional slice for offline CI) |
| `raw_smard_prices` | SMARD electricity market data | `(timestamp_utc, market_zone)` | German hourly/quarter-hour electricity price & load reference |
| `raw_ecb_fx_rates` | ECB Data Portal | `(currency_pair, observation_date)` | `CHF/EUR`, `PLN/EUR`, `USD/EUR`; weekends/holidays naturally absent |
| `raw_charging_sessions` | Deterministic generator anchored to real station IDs | `(session_id, event_seq)` | Includes duplicates, 48h late settlements, refunds, negative-kWh dirty rows, DST edge cases |
| `raw_roaming_settlements` | Mock paginated REST API | `(settlement_id)` | Cursor-paginated JSON batches; tests retry, resume, and schema-drift quarantine |
| `raw_tariff_plans` | Deterministic tariff schedule | `(tariff_id, effective_from)` | Time-varying per-kWh & roaming fees feeding SCD Type 2 snapshots |

Records failing required-column or type-parse contracts at ingestion are routed to `raw_quarantine` with `reject_reason` and `_batch_id` rather than silently dropped.

## 2. Target Kimball star schema (`marts`)

| Model | Type | Grain | Key invariants |
|---|---|---|---|
| `dim_stations_scd2` | Snapshot / Dimension | `(station_sk)` (`dbt_scd_id`) | SCD Type 2 (`dbt_valid_from`, `dbt_valid_to`) tracking capacity kW & operator changes |
| `dim_tariffs_scd2` | Snapshot / Dimension | `(tariff_sk)` | SCD Type 2 tracking price-per-kWh and roaming fee regimes |
| `dim_date` | Dimension | `(date_day)` | Calendar attributes + German holiday flags |
| `fct_charging_sessions` | Fact (Incremental) | `(session_id)` | One reconciled row per session; point-in-time joined to `dim_stations_scd2` and `dim_tariffs_scd2`; amounts normalized to EUR |
| `fct_daily_revenue` | Fact (Contract + Versioned) | `(revenue_date, country_code, operator_id)` | Daily session count, total kWh, gross/net EUR, wholesale electricity cost, gross margin |

## 3. Core invariants

1. **Revenue conservation:** for every reconciled batch window, `sum(valid raw charging EUR + roaming adjustments) == sum(fct_charging_sessions.net_amount_eur)` within `0.00` EUR, and rejected records are fully accounted for in `raw_quarantine`.
2. **48-hour late-arrival merge:** incremental models re-process `[max_event_date - 2 days, current_watermark]` using `unique_key='session_id'` (`merge` strategy) and must match `--full-refresh` row-for-row.
3. **Point-in-time SCD Type 2 join:** sessions join to `dim_stations_scd2` and `dim_tariffs_scd2` where `session_started_at >= dbt_valid_from AND (session_started_at < dbt_valid_to OR dbt_valid_to IS NULL)`, ensuring historical prices never shift retroactively.
4. **Cross-warehouse portability:** SQL uses dbt cross-db macros (`dbt.dateadd`, `dbt.datediff`, `dbt.date_trunc`) and target-conditional partitioning so DuckDB and BigQuery produce identical logical results.
