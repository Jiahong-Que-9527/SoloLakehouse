# Reference workload · charging forecast

<!-- [魏征·2026-11-21] Define the synthetic workload and the prediction task contract. -->

The workload is a synthetic electric-vehicle charging network and the daily forecasting task run on it. All source for the Mlops-engineering project lives in this tree; stage directories hold designs and evidence only.

## Domain

- 40 charging stations in 6 districts, hourly demand in kWh, two years (2025-01-01 through 2026-12-31, UTC).
- Station attributes: `capacity_kW`, district, POI category (office, retail, residential, highway).
- Demand drivers: weekly and daily seasonality, commute patterns by POI category, weather sensitivity (temperature, precipitation), holidays and nearby events, tariff level with step changes.
- Weather exists twice: realized hourly observations and day-ahead forecasts issued at 06:00 Europe/Berlin with realistic error. A model may only ever see the forecast side at issue time; the realized side exists for backtesting and monitoring.

## Regimes (injected by the generator)

- 2026-04-01: tariff step change on a station subset (price-elasticity response).
- 2026-07-14 to 2026-07-20: heatwave week shifting demand timing.
- 2026-10-01: three new stations appear mid-series (cold-start behavior).
- A seeded anomaly mode produces stale or missing forecast files for monitoring drills.

## Prediction task

Issue at 06:00 Europe/Berlin the next-day hourly demand per station (24 hours; extension to 48 hours is a documented option). The availability table lives in the [feature contract](../docs/feature-contract.md) and is binding for every stage.

## Packages (reserved)

| Package | Purpose | Introduced |
|---|---|---|
| `charging_forecast.generator` | Seeded synthetic data and regime injection | M01 |
| `charging_forecast.contract` | Schemas, availability table, release manifests | M01 |
| `charging_forecast.validation` | Dataset validation suite: schema, ranges, continuity, regime invariants | M01 |
| `charging_forecast.features` | Point-in-time transforms and materialization | M02 |
| `charging_forecast.eval` | Backtest folds, metrics, report rendering | M03 |
| `charging_forecast.training` | Model definitions, search, MLflow runs | M04 |
| `charging_forecast.pipeline` | The idempotent CLI steps | M05 |
| `charging_forecast.serving` | Batch scoring and the HTTP API | M06 |
| `charging_forecast.monitoring` | Residual and drift metrics, push path | M07 |
| `charging_forecast.orchestration` | Dagster assets and jobs around the CLI | M08 |

Raw generated data, MLflow state and model artifacts stay outside Git. Code, schemas, manifests, reports and evidence are committed. The generator must be deterministic: the same seed and config produce byte-identical outputs.
