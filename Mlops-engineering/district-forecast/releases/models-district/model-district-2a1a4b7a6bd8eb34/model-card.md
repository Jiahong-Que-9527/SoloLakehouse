# Model card · model-district-2a1a4b7a6bd8eb34

## 1. Identification

- Model: district charging-demand forecaster, release `model-district-2a1a4b7a6bd8eb34`.
- Registry: local release manifest at
  `releases/models-district/model-district-2a1a4b7a6bd8eb34/manifest.json`
  (no MLflow registry in this workload; the manifest is the release).
- Git SHA: `f342272d5c06f322aeba1e4482ad5265d1373f9e`.
- Data release: `dataset-district-v001` (derived from the pinned
  `dataset-v001`, lineage recorded by manifest SHA-256).
- Feature release: `feat-d1-dataset-district-v001`
  (manifest `834efed0…3576`).
- Card date: 2026-11-23.

## 2. Intended use

- Supports next-day hourly demand planning per district, issued at
  06:00 Europe/Berlin for the following UTC day (6 districts × 24 hours).
- Not for per-station or per-connector decisions — that is the first
  workload's task; this model answers at district grain only.

## 3. Training data

- `dataset-district-v001`: the pinned station-grain release aggregated to
  district-hour; `available_at` is the max over contributing stations.
- Period: 2025-01-01 → 2026-12-30 (window of the source release).
- Labels: realized district-hour kWh; 100,368 labeled protocol rows,
  4,464 excluded (rows with unreadable lag features in the first days
  and skipped fold months).
- Features: calendar, per-district statics, published tariff schedule,
  day-ahead weather forecasts (readable at T), demand lags anchored at
  the issue time (24 h / 168 h), 7-day rolling mean over
  [T − 168 h, T − 2 h], days since window start.

## 4. Evaluation

- Protocol: 23 rolling monthly folds, 1-day embargo, 2025-01 skipped
  (insufficient training history) — identical shape to the M03 protocol.
- Headline: pooled MAE **22.338 kWh** (RMSE 36.157, sMAPE 4.59).
- Baselines (same protocol): district seasonal-naive 30.980 kWh,
  district median 33.629 kWh.
- Gate: promoted — strictly beats both baselines
  (22.338 < 30.980 and 22.338 < 33.629).

## 5. Limitations

- Synthetic domain: regimes (tariff step, heatwave, station activation)
  exist in the source data but no drift drill has been run at district
  grain; the monitor stack is not wired for this workload.
- Tree ensembles cannot extrapolate: a demand trend the features do not
  encode would systematically under-predict (observed during onboarding
  with a trended fixture).
- District aggregation hides within-district heterogeneity; error at
  small districts counts more per station.
- A real deployment would add serving, monitoring and a promotion
  rollback drill — all intentionally out of M09 scope.

## 6. Maintenance

- Retraining triggers: none wired (monitoring stays with the reference
  workload); monthly re-run of `run-pipeline` regenerates the protocol
  and, for changed inputs, a new candidate through the same gate.
- Rollback: there is no serving pin in this workload; the reference
  workload's `model-v001` pin is untouched by every operation here.
- Reruns are idempotent: identical inputs reuse every step (verified at
  full scale, 0.86 s vs 54 s fresh).
