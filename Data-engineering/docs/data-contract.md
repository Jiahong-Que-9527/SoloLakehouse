# Data contract and dimensional model specification

<!-- [Antigravity·2026-11-23] Initialize source contracts, star-schema grains, and invariants. -->
<!-- [Antigravity·2026-11-23] Expand column-level schemas, quarantine reasons, and SQL portability rules. -->
<!-- [ZCode·2026-11-23] v1.1: unify conservation semantics (latest-event-per-session), fix FX direction to ECB base notation, define refund/energy rules, revenue_date timezone, dedup rule, wholesale-cost formula and rounding policy; add current-state dimensions, ERD, golden example, and contract changelog. -->

**Contract version:** 1.1 (2026-11-23) — changelog in [§5](#5-contract-changelog). All dbt contracts, tests, and unit-test fixtures must reference this document; a semantic change to any grain, type, or invariant below requires a version bump here first.

## 1. Raw source tables

Every ingested raw table carries four required lineage columns:
- `_batch_id` (`STRING`, non-null): deterministic batch identifier (`<source>-<window>-<seq>`).
- `_ingested_at` (`TIMESTAMP`, non-null): UTC ingestion timestamp.
- `_source_name` (`STRING`, non-null): source identifier (`bnetza_open_data`, `smard_api`, `ecb_portal`, `charging_sim`, `roaming_api`).
- `_source_hash` (`STRING`, non-null): SHA-256 of the source file or API page payload.

**Field semantics common to all commerce tables:**

- `country_code` is the **billing market** of the session (`DE` → `EUR`, `CH` → `CHF`, `PL` → `PLN`), i.e. the currency market the customer is billed in — not the physical station location. All stations are German (`raw_stations_bnetza`); `CH`/`PL` sessions are roaming sessions billed through the clearing hub.
- `energy_kwh` is a **physical measurement and is never negative**. A negative value is always a generator-injected dirty row and must be quarantined (`negative_energy_kwh`) — refunds reverse *amounts*, never energy.
- Refunds and reversals are expressed as **negative amount columns** (`gross_amount_local`, `roaming_fee_local`) on a `refund` / `late_adjustment` event, never as negative energy.

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
Source: ECB Data Portal daily reference rates (ECB quotes `1 EUR` as base, as published).
Grain: `(currency_pair, observation_date)`.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `currency_pair` | `STRING` | No | `EUR/CHF`, `EUR/PLN`, `EUR/USD` (ECB base notation) |
| `observation_date` | `DATE` | No | ECB business day (weekends/TARGET2 holidays absent) |
| `rate` | `DECIMAL(12,6)` | No | Units of foreign currency per `1 EUR` (e.g. `EUR/CHF = 0.941000` means `1 EUR = 0.941 CHF`) |

**Conversion rule (single direction, applied everywhere):** `amount_eur = ROUND(amount_local / rate, 2)`. Never multiply by the reciprocal; never chain conversions through a third currency.

### 1.4 `raw_charging_sessions`
Source: Seeded generator anchored to real `raw_stations_bnetza.station_id` keys.
Grain: `(session_id, event_seq)`.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `session_id` | `STRING` | No | Unique charging session identifier |
| `event_seq` | `INTEGER` | No | Monotonic event sequence (`1` initial event, `2` late settlement / correction / reversal) |
| `station_id` | `STRING` | No | Foreign key to `raw_stations_bnetza.station_id` |
| `tariff_id` | `STRING` | No | Foreign key to `raw_tariff_plans.tariff_id` |
| `country_code` | `STRING` | No | Billing market: `DE`, `CH`, `PL` |
| `currency_code` | `STRING` | No | `EUR`, `CHF`, `PLN` (determined by `country_code`) |
| `session_started_at` | `TIMESTAMP` | No | UTC start timestamp (covers CET/CEST DST transitions) |
| `session_ended_at` | `TIMESTAMP` | No | UTC end timestamp |
| `settled_at` | `TIMESTAMP` | No | UTC settlement availability time (can lag up to 48h) |
| `energy_kwh` | `DECIMAL(12,4)` | No | Delivered energy, always `>= 0`; `< 0` is a generator-injected dirty row quarantined in E01 |
| `gross_amount_local` | `DECIMAL(12,2)` | No | Session energy/time charge in `currency_code`; negative for `refund`/reversal events |
| `event_type` | `STRING` | No | `charge`, `late_adjustment`, `refund` |

### 1.5 `raw_roaming_settlements`
Source: Mock paginated REST API (`/v1/settlements?cursor=...`).
Grain: `(settlement_id)`.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `settlement_id` | `STRING` | No | Unique roaming clearing record |
| `session_id` | `STRING` | No | References `raw_charging_sessions.session_id` |
| `roaming_partner` | `STRING` | No | Clearing hub / eMSP partner ID |
| `roaming_fee_local` | `DECIMAL(12,2)` | No | Roaming surcharge actually billed with the session, in `currency_code`, signed (`>= 0` for charges, negative on refunds) |
| `currency_code` | `STRING` | No | `EUR`, `CHF`, `PLN` |
| `settled_at` | `TIMESTAMP` | No | UTC clearing timestamp |

**Fee provenance:** `raw_tariff_plans.roaming_surcharge_eur` is the *list price* the generator uses to *produce* settlement fees; `raw_roaming_settlements.roaming_fee_local` is the *billed* amount and is the authoritative input for `fct_charging_sessions.roaming_fee_eur`. Downstream models must never read the surcharge from tariffs.

### 1.6 `raw_tariff_plans`
Source: Deterministic tariff schedule.
Grain: `(tariff_id, snapshot_date)`.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `tariff_id` | `STRING` | No | Tariff plan identifier |
| `snapshot_date` | `DATE` | No | Snapshot effective date (`t0`, `t1`, `t2`) |
| `price_per_kwh_eur` | `DECIMAL(10,4)` | No | Retail rate in EUR/kWh |
| `roaming_surcharge_eur` | `DECIMAL(10,2)` | No | Fixed roaming surcharge in EUR (list price, see fee provenance above) |
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

Quarantined rows never enter any Raw table and are excluded from revenue conservation; they are accounted for separately by count and amount in every reconciliation record (§3.1).

## 2. Target Kimball star schema (`marts`)

```text
                     dim_date (date_day)
                           |
raw_stations_bnetza --[dbt snapshot]--> dim_stations_scd2 --(dbt_valid_to IS NULL)--> dim_stations (current)
raw_tariff_plans    --[dbt snapshot]--> dim_tariffs_scd2  --(dbt_valid_to IS NULL)--> dim_tariffs (current)
                           |                                  |
raw_charging_sessions      |  point-in-time join on           |
  (latest event/session)   |  session_started_at              |
        +------------------+---------------+------------------+
        v                                  v
   fct_charging_sessions (grain: session_id)
        |
        +--> fct_daily_revenue v1 / v2 (grain: revenue_date, country_code, operator_name)
```

| Model | Materialization | Grain | Contracted columns |
|---|---|---|---|
| `dim_stations_scd2` | Snapshot (SCD2) | `(station_sk)` | `station_sk`, `station_id`, `operator_name`, `city`, `federal_state`, `postal_code`, `nominal_power_kw`, `connector_count`, `dbt_valid_from`, `dbt_valid_to` |
| `dim_tariffs_scd2` | Snapshot (SCD2) | `(tariff_sk)` | `tariff_sk`, `tariff_id`, `plan_tier`, `price_per_kwh_eur`, `roaming_surcharge_eur`, `dbt_valid_from`, `dbt_valid_to` |
| `dim_stations` | View over `dim_stations_scd2` | `(station_id)` | All `dim_stations_scd2` columns except `dbt_valid_from`/`dbt_valid_to`, filtered to `dbt_valid_to IS NULL` (current state per station) |
| `dim_tariffs` | View over `dim_tariffs_scd2` | `(tariff_id)` | All `dim_tariffs_scd2` columns except `dbt_valid_from`/`dbt_valid_to`, filtered to `dbt_valid_to IS NULL` (current state per tariff) |
| `dim_date` | Table | `(date_day)` | `date_day`, `year_num`, `month_num`, `day_of_week`, `is_weekend`, `is_de_holiday` |
| `fct_charging_sessions` | Incremental (`merge`) | `(session_id)` | `session_id`, `station_sk`, `tariff_sk`, `revenue_date`, `country_code`, `currency_code`, `fx_rate_to_eur`, `fx_rate_status`, `energy_kwh`, `gross_amount_eur`, `roaming_fee_eur`, `net_amount_eur`, `wholesale_cost_eur`, `gross_margin_eur`, `event_type`, `settled_at` |
| `fct_daily_revenue` (`v1`) | Table (Contract) | `(revenue_date, country_code, operator_name)` | `revenue_date`, `country_code`, `operator_name`, `session_count`, `total_energy_kwh`, `gross_amount_eur`, `roaming_fee_eur`, `net_amount_eur` |
| `fct_daily_revenue` (`v2`) | Table (Contract) | `(revenue_date, country_code, operator_name)` | All `v1` columns + `wholesale_cost_eur`, `gross_margin_eur` (non-breaking additive change) |

**Build-order note:** `dim_stations` / `dim_tariffs` materialize from the latest raw snapshot (`t0/t1/t2`) in `E02`–`E03` and become views over the SCD2 tables once `E04` lands; the contracted column list is identical in both phases, so no contract change is required at the `E04` transition.

**Derived column definitions (binding for all marts):**

- `revenue_date` = civil date of `session_started_at` converted to **`Europe/Berlin`** local time (the physical market of all stations), not UTC. This is the daily-grain attribute and the BigQuery partition key.
- `gross_amount_eur` = `ROUND(gross_amount_local / fx_rate_to_eur, 2)`; `roaming_fee_eur` = `ROUND(roaming_fee_local / fx_rate_to_eur, 2)` (`0.00` for `DE` sessions with no settlement row).
- `net_amount_eur` = `gross_amount_eur + roaming_fee_eur` (both components signed).
- `wholesale_cost_eur` = `ROUND(energy_kwh * wholesale_eur_mwh / 1000, 2)`, priced from the `DE-LU` SMARD hour containing `session_started_at` (UTC). Wholesale cost reflects physical delivery at German stations and is computed identically for all billing markets; it carries the sign of the event (positive for `charge`/`late_adjustment`, negative for `refund`).
- `gross_margin_eur` = `net_amount_eur - wholesale_cost_eur`.
- `fx_rate_to_eur` = latest ECB `rate` for the session's currency pair with `observation_date <= revenue_date` (`1.000000` for `EUR` sessions).
- `operator_name` in `fct_daily_revenue` is resolved **point-in-time** through `station_sk → dim_stations_scd2` (the operator valid at `session_started_at`), so historical daily revenue never shifts when operators change.

## 3. Core invariants and SQL rules

1. **Revenue conservation (canonical form):** for every reconciled batch window,
   `SUM(net_amount_eur recomputed from valid raw events, latest event per session) == SUM(fct_charging_sessions.net_amount_eur)`
   with `0.00` EUR tolerance. "Recomputed from valid raw events" means: drop quarantined rows, reduce `raw_charging_sessions` to the latest `event_seq` per `session_id` (§3.2), normalize amounts per §2 rounding rules, then sum. Quarantined rows are excluded from both sides and reported separately (count + `gross_amount_local` sum) in every evidence record.
2. **Latest-event semantics and dedup:** `stg_charging_sessions` keeps exactly one row per `session_id`: highest `event_seq` wins; ties (same `event_seq` ingested more than once) resolve by highest `_ingested_at`, then highest `_source_hash` for determinism. Byte-identical duplicate payloads (same business values and `_source_hash`) are dropped in staging and are *not* quarantined; surviving rows must pass a `unique(session_id, event_seq)` generic test.
3. **Rounding and precision:** every local→EUR normalization divides by `fx_rate_to_eur` once and rounds half-up to 2 decimals; mart columns are computed **independently from raw values**, never by re-rounding another mart column, so repeated builds never accumulate cent drift.
4. **Revenue attribution timezone:** `revenue_date` is the `Europe/Berlin` civil date of `session_started_at` (see §2). All other timestamps (`settled_at`, `_ingested_at`, freshness) remain UTC.
5. **48-hour late-arrival incremental merge:** `fct_charging_sessions` filters incoming events with `settled_at >= dbt.dateadd('day', -2, max_settled_at)` (or bounded `--vars` `start_date`/`end_date` during backfill), merges on `unique_key='session_id'` (latest event replaces the stored row), and must match `dbt build --full-refresh` row-for-row.
6. **Point-in-time SCD Type 2 join:** sessions join to `dim_stations_scd2` and `dim_tariffs_scd2` on `session_started_at >= dbt_valid_from AND (session_started_at < dbt_valid_to OR dbt_valid_to IS NULL)`.
7. **ECB holiday FX carry-forward:** non-EUR sessions join to the latest ECB observation date `<= revenue_date`, explicitly labeling `fx_rate_status` as `observed` (observation on `revenue_date`) or `carried_forward` (latest earlier observation; weekends/TARGET2 holidays). Rates are never interpolated and future dates are never used.
8. **Wholesale cost pricing:** the SMARD `DE-LU` price hour is selected by UTC hour of `session_started_at` (`timestamp_utc <= session_started_at < timestamp_utc + interval` of the price resolution); sessions before the first available price hour use the earliest available price with `fx_rate_status`-style explicit labeling left to the model implementation. Wholesale cost is independent of the billing market (§2).
9. **Cross-warehouse SQL portability:** all date math, casting, timezone conversion, safe division, and BigQuery partitioning/clustering live in shared dbt macros under `dbt_project/macros/` so `duckdb` and `bigquery` execute the same model definitions.

## 4. Golden example (binding for unit-test fixtures)

One CH roaming session, from raw rows to mart row. These exact numbers must be reproducible by the seeded generator and asserted by E03 `unit_tests`.

**Inputs**

| Artifact | Value |
|---|---|
| ECB `EUR/CHF`, `observation_date = 2026-03-02` | `rate = 0.941000` (CHF per 1 EUR; 2026-03-02 is an ECB business day → `observed`) |
| Tariff `T-ROAM-CH` (`t0`) | `price_per_kwh_eur = 0.5900`, `roaming_surcharge_eur = 1.50` |
| SMARD `DE-LU`, hour `2026-03-02 18:00 UTC` | `wholesale_eur_mwh = 95.00` |
| Session `S-CH-0001` | station `BNA-F-0001` (50 kW), billing market `CH`/`CHF`, started `2026-03-02 18:30 UTC` (19:30 CET), ended `19:15 UTC`, settled `2026-03-03 20:00 UTC` (25.5h later) |

**Event 1 — `charge` (`event_seq = 1`)**

| Raw row | `energy_kwh = 45.2000`, `gross_amount_local = 25.09` CHF (`45.2 × 0.59 × 0.941 = 25.0946 → 25.09`), settlement fee `roaming_fee_local = 1.41` CHF (`1.50 × 0.941 = 1.4115 → 1.41`) |
|---|---|
| `revenue_date` | `2026-03-02` (18:30 UTC → 19:30 Europe/Berlin, same civil date) |
| Mart row | `fx_rate_to_eur = 0.941000`, `fx_rate_status = observed`, `gross_amount_eur = 26.67` (`25.09 / 0.941 = 26.6674`), `roaming_fee_eur = 1.50` (`1.41 / 0.941 = 1.4984`), `net_amount_eur = 28.17`, `wholesale_cost_eur = 4.29` (`45.2 × 95 / 1000 = 4.294`), `gross_margin_eur = 23.88` |

**Event 2 — `late_adjustment` (`event_seq = 2`, settled `2026-03-04 12:00 UTC`, inside the 48h lookback)**

| Raw row | corrected `energy_kwh = 44.8000`, `gross_amount_local = 24.87` CHF (`44.8 × 0.59 × 0.941 = 24.8725`), fee unchanged `1.41` CHF |
|---|---|
| Mart row after merge | `gross_amount_eur = 26.43`, `roaming_fee_eur = 1.50`, `net_amount_eur = 27.93`, `wholesale_cost_eur = 4.26`, `gross_margin_eur = 23.67`; the `event_seq = 1` row is replaced (merge on `session_id`) |

**Event 3 — full `refund` (`event_seq = 2` on a twin session `S-CH-0002`)**

| Raw row | `energy_kwh = 45.2000` (physical energy stays positive), `gross_amount_local = -25.09`, `roaming_fee_local = -1.41` |
|---|---|
| Mart row | `gross_amount_eur = -26.67`, `roaming_fee_eur = -1.50`, `net_amount_eur = -28.17`, `wholesale_cost_eur = -4.29`, `gross_margin_eur = -23.88` |

**Conservation check for this batch window:** left side recomputes `27.93 (S-CH-0001, latest event) + (-28.17) (S-CH-0002) = -0.24`; right side must equal `-0.24` exactly. The quarantined dirty rows of the same batch are reported by count and amount, never inside this sum.

## 5. Contract changelog

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-11-23 | Initial scaffold (Antigravity): raw schemas, star-schema grains, invariants, SQL portability rules. |
| 1.1 | 2026-11-23 | Pre-implementation clarifications (ZCode): unified revenue-conservation formula with latest-event-per-session semantics; refund = negative amounts, `energy_kwh` never negative; FX moved to ECB base notation (`EUR/CHF`) with single-direction conversion; `revenue_date` pinned to `Europe/Berlin`; staging dedup rule promoted from E02 design to contract; `wholesale_cost_eur`/`gross_margin_eur` defined; rounding policy fixed; current-state `dim_stations`/`dim_tariffs` defined as views over SCD2; point-in-time `operator_name`; fee provenance (tariff list price vs billed settlement); golden example and ERD added. |
