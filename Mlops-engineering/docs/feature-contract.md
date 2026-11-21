# Feature contract (v1 draft)

<!-- [魏征·2026-11-21] Draft the point-in-time feature contract; finalize at M02. -->

This contract defines what a feature row means, when it becomes available and how leakage is tested. M02 implements it as code; when code and text disagree, this file is authoritative.

## Identity and time

| Field | Meaning |
|---|---|
| `station_id` | Entity key. One row per station and hour. |
| `hour_utc` | Event time: the hour the row describes. |
| `available_at` | The earliest issue time at which this row is complete, per the family rules below. |

A model issued at `T` (06:00 Europe/Berlin) may read only rows with `available_at <= T`.

## Feature families

| Family | Examples | Availability rule |
|---|---|---|
| Calendar | hour, weekday, holiday flag, school break | Known from the calendar; available at the start of the day it describes. |
| Station attributes | `capacity_kW`, district, POI category | Static per dataset release; never time-varying in v1. |
| Demand lags and rolling | demand 24h/168h ago, 7-day rolling mean | Available at issue time only if the lagged hour closed before `T` minus the ingestion delay. |
| Weather forecasts | temperature, precipitation for the target hour | Only the forecast issued before `T`, joined by forecast reference time; realized weather is never a feature. |
| Tariff and events | price per kWh, nearby event flags | Known from published schedules ahead of the target day. |

## Rules

1. One transform, two entry points. Training and serving read features through the same code path; serving may not recompute features with different logic.
2. Features are materialized to Parquet with a manifest (schema version, source data release ID, row counts, checksums) and are reproducible from the data release ID.
3. The feature schema is versioned. Adding a column is a minor version; changing or removing one is a major version and requires retraining.
4. Every feature traces to the generator outputs it derives from; the mapping is written into this file when the family is added.

## Leakage tests (implemented at M02)

- Shift test: moving every `available_at` forward by one step changes nothing for an issue at `T`; moving it backward makes the affected rows unreadable, and the loader rejects them.
- Forecast test: a forecast row joined with the wrong reference time is rejected by the loader.
- Duplicate test: two materializations from the same data release ID produce byte-identical Parquet and manifests.
