# Data contract and dimensional model specification

<!-- [Antigravity·2026-11-23] Initialize source contracts, star-schema grains, and invariants. -->
<!-- [Antigravity·2026-11-23] Expand column-level schemas, quarantine reasons, and SQL portability rules. -->

## 1. Raw source tables

Every ingested raw table carries four required lineage columns:
- `_batch_id` (`STRING`, non-null): deterministic batch identifier (`<source>-<window>-<seq>`).
- `_ingested_at` (`TIMESTAMP`, non-null): UTC ingestion timestamp.
- `_source_name` (`STRING`, non-null): source identifier (`bnetza_open_data`, `smard_api`, `ecb_portal`, `charging_sim`, `roaming_api`).
- `_source_hash` (`STRING`, non-null): SHA-256 of the source file or API page payload.

### 1.1 `raw_stations_bnetza`
Source: Bundesnetzagentur Ladesäulenregister (`CC BY 4.0`, Hesse/Frankfurt regional slice) + `t0/t1/t2` snapshots.
Grain: `(station_id, snapshot_date)`.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `station_id` | `STRING` | No | Natural station key (`BNetzA` ID) |
| `snapshot_date` | `DATE` | No | Snapshot observation date (`t0`, `t1`, `t2`) |
| `operator_name` | `STRING` | No | Charge point operator (`Betreiber`) |
| `postal_code` | `STRING` | Yes | German 5-digit PLZ |
| `city` | `STRING` | Yes | Municipality (`Ort`) |
| `federal_state` | `STRING` | No | German state (`Bundesland`) |
| `latitude` | `DECIMAL(9,6)` | Yes | WGS84 latitude |
| `longitude` | `DECIMAL(9,6)` | Yes | WGS84 longitude |
| `nominal_power_kw` | `DECIMAL(10,2)` | No | Total installed power (`Nennleistung`) |
| `connector_count` | `INTEGER` | No | Number of charge points (`Anzahl Ladepunkte`) |
| `commissioned_date` | `DATE` | Yes | Official `Inbetriebnahmedatum` |

### 1.2 `raw_smard_prices`
Source: Bundesnetzagentur SMARD wholesale electricity market feed.
Grain: `(timestamp_utc, market_zone)`.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `timestamp_utc` | `TIMESTAMP` | No | Hourly/quarter-hour UTC start |
| `market_zone` | `STRING` | No | `DE-LU` |
| `wholesale_eur_mwh` | `DECIMAL(10,4)` | No | Wholesale day-ahead price in EUR/MWh |
| `grid_load_mwh` | `DECIMAL(12,2)` | Yes | Realized German load in MWh |

### 1.3 `raw_ecb_fx_rates`
Source: ECB Data Portal daily reference rates.
Grain: `(currency_pair, observation_date)`.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `currency_pair` | `STRING` | No | `CHF/EUR`, `PLN/EUR`, `USD/EUR` |
| `observation_date` | `DATE` | No | ECB business day (weekends/TARGET2 holidays absent) |
| `rate` | `DECIMAL(12,6)` | No | Units of foreign currency per `1 EUR` |

### 1.4 `raw_charging_sessions`
Source: Seeded generator anchored to real `raw_stations_bnetza.station_id` keys.
Grain: `(session_id, event_seq)`.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `session_id` | `STRING` | No | Unique charging session identifier |
| `event_seq` | `INTEGER` | No | Monotonic event sequence (`1` initial, `2` late settlement/reversal) |
| `station_id` | `STRING` | No | Foreign key to `raw_stations_bnetza.station_id` |
| `tariff_id` | `STRING` | No | Foreign key to `raw_tariff_plans.tariff_id` |
| `country_code` | `STRING` | No | `DE`, `CH`, `PL` |
| `currency_code` | `STRING` | No | `EUR`, `CHF`, `PLN` |
| `session_started_at` | `TIMESTAMP` | No | UTC start timestamp (covers CET/CEST DST transitions) |
| `session_ended_at` | `TIMESTAMP` | No | UTC end timestamp |
| `settled_at` | `TIMESTAMP` | No | UTC settlement availability time (can lag up to 48h) |
| `energy_kwh` | `DECIMAL(12,4)` | No | Delivered energy (`< 0` injected as dirty row in E01) |
| `gross_amount_local` | `DECIMAL(12,2)` | No | Gross charge or negative refund in `currency_code` |
| `event_type` | `STRING` | No | `charge`, `late_adjustment`, `refund` |

### 1.5 `raw_roaming_settlements`
Source: Mock paginated REST API (`/v1/settlements?cursor=...`).
Grain: `(settlement_id)`.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `settlement_id` | `STRING` | No | Unique roaming clearing record |
| `session_id` | `STRING` | No | References `raw_charging_sessions.session_id` |
| `roaming_partner` | `STRING` | No | Clearing hub / eMSP partner ID |
| `roaming_fee_local` | `DECIMAL(12,2)` | No | Clearing fee in `currency_code` |
| `currency_code` | `STRING` | No | `EUR`, `CHF`, `PLN` |
| `settled_at` | `TIMESTAMP` | No | UTC clearing timestamp |

### 1.6 `raw_tariff_plans`
Source: Deterministic tariff schedule.
Grain: `(tariff_id, snapshot_date)`.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `tariff_id` | `STRING` | No | Tariff plan identifier |
| `snapshot_date` | `DATE` | No | Snapshot effective date (`t0`, `t1`, `t2`) |
| `price_per_kwh_eur` | `DECIMAL(10,4)` | No | Retail rate in EUR/kWh |
| `roaming_surcharge_eur` | `DECIMAL(10,2)` | No | Fixed roaming surcharge in EUR |
| `plan_tier` | `STRING` | No | `standard`, `fast_dc`, `fleet` |

### 1.7 `raw_quarantine`
Records failing ingestion schema, nullability, or type-parse rules are written here instead of Raw tables.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `quarantine_id` | `STRING` | No | Deterministic hash of batch + source record |
| `_batch_id` | `STRING` | No | Batch identifier |
| `_source_name` | `STRING` | No | Originating source |
| `raw_payload_json` | `STRING` | No | Original JSON/CSV payload verbatim |
| `reject_reason` | `STRING` | No | Enum: `missing_required_column`, `unexpected_schema_drift`, `invalid_type`, `negative_energy_kwh`, `invalid_timestamp_order`, `null_primary_key` |
| `quarantined_at` | `TIMESTAMP` | No | UTC timestamp |

## 2. Target Kimball star schema (`marts`)

| Model | Materialization | Grain | Contracted columns |
|---|---|---|---|
| `dim_stations_scd2` | Snapshot (SCD2) | `(station_sk)` | `station_sk`, `station_id`, `operator_name`, `city`, `federal_state`, `postal_code`, `nominal_power_kw`, `connector_count`, `dbt_valid_from`, `dbt_valid_to` |
| `dim_tariffs_scd2` | Snapshot (SCD2) | `(tariff_sk)` | `tariff_sk`, `tariff_id`, `plan_tier`, `price_per_kwh_eur`, `roaming_surcharge_eur`, `dbt_valid_from`, `dbt_valid_to` |
| `dim_date` | Table | `(date_day)` | `date_day`, `year_num`, `month_num`, `day_of_week`, `is_weekend`, `is_de_holiday` |
| `fct_charging_sessions` | Incremental (`merge`) | `(session_id)` | `session_id`, `station_sk`, `tariff_sk`, `revenue_date`, `country_code`, `currency_code`, `fx_rate_to_eur`, `fx_rate_status`, `energy_kwh`, `gross_amount_eur`, `roaming_fee_eur`, `net_amount_eur`, `wholesale_cost_eur`, `gross_margin_eur`, `event_type`, `settled_at` |
| `fct_daily_revenue` (`v1`) | Table (Contract) | `(revenue_date, country_code, operator_name)` | `revenue_date`, `country_code`, `operator_name`, `session_count`, `total_energy_kwh`, `gross_amount_eur`, `roaming_fee_eur`, `net_amount_eur` |
| `fct_daily_revenue` (`v2`) | Table (Contract) | `(revenue_date, country_code, operator_name)` | All `v1` columns + `wholesale_cost_eur`, `gross_margin_eur` |

## 3. Core invariants and SQL rules

1. **Revenue conservation:** for every reconciled batch window,
   `SUM(valid raw charging_sessions EUR + roaming_fee EUR) == SUM(fct_charging_sessions.net_amount_eur)` with `0.00` EUR tolerance, and every excluded dirty record is accounted for in `raw_quarantine`.
2. **48-hour late-arrival incremental merge:** `fct_charging_sessions` filters incoming events with `settled_at >= dbt.dateadd('day', -2, max_settled_at)` (or bounded `--vars` `start_date`/`end_date` during backfill), merges on `unique_key='session_id'`, and must match `dbt build --full-refresh` row-for-row.
3. **Point-in-time SCD Type 2 join:** sessions join to `dim_stations_scd2` and `dim_tariffs_scd2` on `session_started_at >= dbt_valid_from AND (session_started_at < dbt_valid_to OR dbt_valid_to IS NULL)`.
4. **ECB holiday FX carry-forward:** non-EUR sessions join to the latest ECB observation date `<= revenue_date`, explicitly labeling `fx_rate_status` as `observed` or `carried_forward` (never interpolating future rates).
5. **Cross-warehouse SQL portability:** all date math, casting, safe division, and BigQuery partitioning/clustering live in shared dbt macros under `dbt_project/macros/` so `duckdb` and `bigquery` execute the same model definitions.
