# M07 · Acceptance evidence

Local WSL2 run on 2026-11-22 UTC. Source checkout
`c1760303b601ae5d71c35c581303a765752564be` plus the M07 changes in this
worktree. Python 3.13.14, uv 0.13.9, MLflow 3.18.0, scikit-learn 1.9.1,
Prometheus 2.53.5+ds1, Pushgateway 1.11.2 and upstream Alertmanager 0.28.1.
The uv lock SHA-256 is
`aca4b621b760f4b9b175333608e2dc26441e0a60c36d6f16bacf84d683b2e57a`.

## A1 · Drift and held-out recovery

Ran [the documented monitor-drill command](../README.md#run-locally) with a
fresh output directory under `data/m07`. The disposable generator config
moved the tariff regime to 2026-10-12, applied a €0.45/kWh surcharge across
all six districts, and ramped elasticity −1.4 over two days. The monitored
shifted issue window was 2026-11-15 with labels through 2026-11-17 01:00 UTC
in replay time. The alert deadline measures wall time from metric push, with
the replay evaluating one chosen window after the regime change.

| Signal | Healthy control | Shifted | Limit |
| --- | ---: | ---: | ---: |
| Residual MAE, kWh | 5.965350 | 48.420077 | 6.706822 |
| Target tariff PSI | 2.695413 | 6.436659 | 2.695413 |
| Target tariff KS | 0.368701 | 1.000000 | 0.368701 |
| Prediction KS | 0.066602 | 0.081982 | 0.164046 |
| Label coverage | 960 / 960 | 960 / 960 | — |

The shifted report recorded 12 drift breaches and a `retrain` decision with
ID `600ac4f9f105fe58b9c9adf5d428346dac45664c9dbefc3d037c19ba9ad5211a`.
The candidate used the pinned hyperparameters and 610,704 available
training labels through issue 2026-11-15. Both models scored the same 6,720
labeled rows on the seven issue days from 2026-11-18 through 2026-11-24.
Pooled pinned MAE was **41.905948 kWh** and candidate MAE was **2.481012 kWh**.
The artifact SHA-256 and metrics matched on repeated runs. The deployment
pin remained `model-v001`.

The drill used `dataset-m07-tariff-drill` with manifest SHA-256
`2fdd716aeb54b4267c1a8bb801f5be0ac76a3e38b9cf5e4a7b0e9d48f43889ad` and
feature manifest SHA-256
`3af2e3052fef7b3ea73db1494c218021e5018f73bad8ea780b951411e8e08d40`.
The score manifest SHA-256 was
`02dcbd42e84c1dc4863b24ed87afb8d2894a1fd5f1b768be420b2b97462db42f`.
Candidate `model-m07-600ac4f9f105` artifact SHA-256 was
`55fbd315611a009e55c4f503466b878babf20f53ba655be343db1b062d57102a`.
The final SQLite MLflow run ID was `3905d7eb2777404e85e52ee00ce551ec`.

| Wall-clock event | UTC on 2026-11-22 |
| --- | --- |
| Generate the shifted dataset | 23:31:59.547 |
| First shifted monitor report | 23:32:08.798 |
| Push shifted metrics | 23:32:25.682 |
| Webhook receives firing alert | 23:32:33.549 |
| Start candidate training | 23:32:33.692 |
| Finish training and write candidate artifact | 23:32:49.240 |

Webhook delivery took **7.87 seconds** from metric push against the 30-second
deadline. The recovery check scored the candidate on the held-out week.

## A2 · Receiver and healthy control

Prometheus scraped the healthy 2026-12-30 issue with no pending or firing
alerts and no webhook during the 10-second observation. Its decision was
`hold`. The control used `dataset-v001`, `feat-v1-dataset-v001`, and score
manifest SHA-256
`cd1200a47802ef2b91377d2246ccd9a31d82b4abbe9e8034e0706383ad4ced21`.
Between 23:32:15.679 and 23:32:25.682 UTC the healthy scrape produced no
alerts. The shifted replay then delivered one `ChargingForecastDrift`
webhook group with 12 firing signals.

For the input-quality rule, replayed the healthy report with only
`demand.demand_lag_168h.missing` changed to 0.50 against a calibrated limit
of 0.075. The policy held retraining and the receiver logged
`ChargingForecastInputQuality` at 23:35:33.548 UTC.

A separate replay with the generator's `anomaly_mode` confirmed that the
2026-10-08 issue stopped in feature construction when all 24 forecast hours
for a district were missing. No completed score window existed for M07 to
evaluate. The M08 orchestration failure path is responsible for surfacing
that upstream failure.

## A3 · Measured thresholds

The [threshold derivations](calibration-thresholds.json) record the M03,
model, feature and dataset manifest hashes, 296,592 reference rows, 364
calibration windows and the measured date, count, maximum and limit for
each of 51 signals. The reproducible full calibration includes reference
distributions and stays in the run output. Its SHA-256 was
`0318b943cec68a89ee2c4ac548c9857e34d2017070f35c9a54029e18ebd39914`
on repeated runs.

## Local checks

The automated checks cover mature and partial label windows, verified score
Parquet, drift and calendar decisions, missing-input holds and manual
override, and unseen and missing categorical buckets.

The full workload suite passed all 69 tests in 258.01 seconds with
`uv run --locked --offline --no-sync pytest` in the local environment.
Two dependency deprecation warnings came from Starlette's TestClient and
MLflow's SQLAlchemy loader. Ruff lint and format checks passed.
