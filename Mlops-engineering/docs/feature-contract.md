# Feature contract (v1)

<!-- [魏征·2026-11-21] Draft the point-in-time feature contract. -->
<!-- [魏征·2026-11-22] Finalize v1 at M02: target window, calendar and tariff
     schedule readability, lag anchoring and the forecast boundary are now
     binding. Resolutions are recorded in docs/delivery-plan.md (M02 entry). -->

This contract defines what a feature row means, when it becomes available and how leakage is tested. `charging_forecast.features` implements it as code; when code and text disagree, this file is authoritative.

## Identity and time

| Field | Meaning |
|---|---|
| `station_id` | Entity key. One feature row per station and target hour. |
| `hour_utc` | Event time: the target hour the row describes. |
| `available_at` | The issue time `T` at which this row became complete. Every feature row carries `available_at == T`; the loader serves only rows with `available_at <= T`. |

The issue time `T` is 06:00 Europe/Berlin on issue day `D` (05:00 UTC in winter, 04:00 in summer). The **target window** is the next UTC calendar day: the 24 hours `[D+1 00:00Z, D+1 23:00Z]`. It is anchored to UTC days because the dataset's day-ahead forecasts are issued per UTC reference day; the Berlin-anchored alternative would straddle two forecast issues and break the join. Valid issue days run from the release window start to the window end minus one day.

## Feature families

| Family | Feature columns | Availability rule | Stamp is the readability bound |
|---|---|---|---|
| Calendar | `hour_of_day`, `day_of_week`, `is_public_holiday`, `is_school_break` | Published calendar: the row for any date in the window is readable at any issue time. | No |
| Station attributes | `district`, `poi_category`, `capacity_kw`, `days_active` | Static per dataset release; a station enters at its `active_from`. | Yes (`active_from <= T`) |
| Demand lags and rolling | `demand_lag_24h`, `demand_lag_168h`, `demand_rolling_7d_mean`, `demand_latest` | Fixed clock windows anchored at `T`: the lagged hour must close before `T` minus the ingestion delay. | Yes (`available_at <= T`) |
| Weather forecasts | `fcst_temperature_c`, `fcst_precipitation_mm` | Only forecasts with `available_at <= T`, joined by `reference_hour_utc`; realized weather is never a feature. | Yes (`available_at <= T`) |
| Tariff and events | `price_current`, `price_at_target`, `is_event_active`, `event_boost` | Published schedules, known ahead of the target day; joined by effectiveness/coverage, not by stamp. | No |

Resolved semantics (binding for every later stage):

1. **Calendar is a published schedule.** Holiday and school-break calendars are known in advance, so the target day's flags are readable at `T` even though the calendar row is stamped with the start of the day it describes. The join key is the target hour's UTC date, matching the generator's demand factors.
2. **Demand lags are anchored at the issue time, not at each target hour.** For day-ahead targets (18–42 h ahead of `T`), a per-target-hour lag-24 h would be unreadable for most target hours. The features are instead fixed windows over readable demand: `demand_latest` at `T - (1 + delay) h`, `demand_lag_24h` at `T - 24 h`, `demand_lag_168h` at `T - 168 h`, and `demand_rolling_7d_mean` over `[T - 168 h, T - (1 + delay) h]`. Windows are fixed clock ranges, so advancing a stamp never changes an already-readable value; delaying one turns the affected values unreadable (NaN).
3. **The forecast boundary is inclusive.** The day-ahead forecast for the target day is issued exactly at `T`; "issued before `T`" means `available_at <= T`. Each target hour must resolve to exactly one readable forecast row (the latest issue at or before `T`); a missing or ambiguous join fails the build loudly.
4. **Tariff and event schedules are readable ahead of the target day** per the frozen M01 decision. `price_at_target` reads the tariff effective at the target hour from the published schedule; `price_current` reads the price in force at `T`. Event coverage mirrors the generator: `start_utc <= hour <= end_utc`, highest `boost` wins.

## Rules

1. One transform, two entry points. Training and serving read features through the same code path (`charging_forecast.features`); serving may not recompute features with different logic.
2. Features are materialized to Parquet with a manifest (schema version, source data release ID, row counts, checksums) and are reproducible from the data release ID. Two materializations from the same inputs are byte-identical; manifests carry no wall-clock values.
3. The feature schema is versioned (`charging-features-v1`). Adding a column is a minor version; changing or removing one is a major version and requires retraining.
4. Every feature traces to the generator outputs it derives from; the mapping is the table above and is kept in sync when a family changes.

## Leakage tests (implemented at M02)

- **Shift test**: delaying every `available_at` by one step makes the affected rows unreadable at `T` — the loader excludes them, and a training split built through any other path is a defect. Advancing every `available_at` by one step changes no feature value, because lag windows are fixed clock ranges. Availability stamping affects readability only, never row content.
- **Forecast test**: a forecast row whose issue time does not match the day-ahead convention for its reference time (issued at 06:00 Europe/Berlin the day before) fails the build; a target hour with no readable forecast row also fails the build.
- **Duplicate test**: two materializations from the same data release ID produce byte-identical Parquet and manifests.
- **Fold check**: for every issue date in a range, an automated check verifies that the split's rows carry `available_at <= T` (in fact `== T`) and that every target hour is strictly after `T`.
