# Model card · charging demand candidate (M04 draft)

<!-- Draft for the candidate selected at M04. From M05 on, every registered
     model release ships a completed copy of docs/model-card-template.md
     next to its manifest; this file is the stage's working draft. -->

## 1. Identification

- Model: `sklearn.HistGradientBoostingRegressor` behind a ColumnTransformer
  pipeline (one-hot categoricals, passthrough numerics; native NaN handling).
- Candidate config: `learning_rate=0.1, max_leaf_nodes=63,
  min_samples_leaf=40`, `max_iter=300`, early stopping off, seed 20261122,
  `OMP_NUM_THREADS=1`.
- Stage: M04 (not registered — M05 registers the winning candidate and
  assigns the release ID, registry version and artifact checksum).
- Git SHA: `8bb3484` (working tree of the M04 branch at run time).
- Training data: `dataset-v001`; features `feat-v1-dataset-v001`.
- Card date: 2026-11-22.

## 2. Intended use

- Decision supported: the day-ahead unit-commitment style planning of
  charging capacity — how much energy each station will deliver in each
  hour of the next UTC day, issued at 06:00 Europe/Berlin.
- Owner: the ML Engineering portfolio (Mlops-engineering); the network
  operations persona consumes the forecast downstream (M06 serving).
- Must not be used for: real-time (intra-hour) control; pricing or revenue
  settlement; any station outside `dataset-v001`'s synthetic domain; hours
  beyond the 24-hour target window.

## 3. Training data

- Data release `dataset-v001` (seeded synthetic EV charging network; 40
  stations, 6 districts, 2025-01-01 through 2026-12-31 UTC), features
  `feat-v1-dataset-v001` (729 issues, 653,904 rows).
- Label: realized hourly demand (kWh) at `(station_id, hour_utc)` for the
  24 target hours of each issue day; coverage is dense in the release.
- Training rows: point-in-time feature rows stamped `available_at == T`,
  read only through the contract's loader path; rows with unreadable labels
  are excluded from fitting.
- Evaluation rows: the M03 protocol's 23 monthly folds (2025-02 … 2026-12,
  embargo 1 day, minimum 14 training issues), 626,376 scored model rows;
  exclusions trace to the three cold-start stations (S038–S040, active from
  2026-10-01) exactly as in the M03 baseline report.

## 4. Evaluation

- Protocol: the M03 harness, unchanged — pooled metrics over the monthly
  rolling-origin folds, refit per fold on all issues up to the fold's last
  training issue; seasonal-naive and per-station-median baselines recomputed
  on identical rows inside the same run (they match the committed M03
  report to the sixth decimal).
- Headline (pooled): model MAE **6.352612** kWh vs station median
  7.689936 (−1.334329, bootstrap 95% CI [−1.353366, −1.315610]) vs
  seasonal naive 9.151699 (−2.799631, CI [−2.824427, −2.774531]).
  Acceptance outcome: **beats the seasonal-naive gate and the stronger
  median baseline — yes, with both confidence intervals excluding zero.**
- Segments: the model wins every district (−0.93 … −1.63 kWh), every
  station (−0.058 … −2.673 kWh) and every hour against the station median;
  no segment regresses. The hardest segments are the evening peak (18:00
  UTC, model MAE 9.741) and high-volume stations (S034, S023, S001 —
  MAE ~10–11 kWh, still −2.1 … −2.7 kWh better than the median).
- Selection: fixed seeded 8-config grid on an internal split (train issues
  ≤ 2026-08-31, validation September 2026; validation MAE 6.086714 for the
  selected config); the protocol folds never touched the selection split.

## 5. Limitations

- Synthetic domain: all structure (seasonality, weather sensitivity, tariff
  elasticity, events, cold starts) is generator-injected; absolute error
  levels do not transfer to real networks, and the model has never seen a
  stale/missing-forecast regime (anomaly mode is drill-only, M07).
- Error concentrates on the evening ramp and on the high-volume stations;
  p99 absolute residual is ~34 kWh, so tail risk on peak hours is real.
- Station identity is not a feature: the model generalizes across stations
  through capacity, POI category and district. A station with an
  unrepresentative attribute mix could underperform (the cold-start trio is
  already the closest segment to a tie).
- The 2026-04 tariff step and the 2026-07 heatwave are in-training regimes
  for late folds; a genuinely unseen regime shift is what M07's monitors
  must catch.
- A real deployment additionally needs: a live feature pipeline with the
  same contract guarantees, forecast-error monitoring at the source, and
  retraining triggers with a rollback path (M05–M08 scope).

## 6. Maintenance

- Retraining triggers: none enforced yet — defined at M07 (residual and
  drift monitors) and automated at M08.
- Monitoring thresholds: none in force yet; the residual summary in the
  committed report (bias +0.074 kWh, mean |residual| 6.356 kWh, p90
  15.482, p99 34.251) is the reference distribution for M07's baselines.
- Last drill: none (M07 scope). Rollback procedure reference: the
  manifest-based rollback of ADR-005, wired at M05/M06.
