# M07 · Monitoring, drift and retraining triggers

<!-- [魏征·2026-11-21] Initialize stage planning. -->

**Status** Accepted locally · [Roadmap](../README.md) · [Evidence guide](../docs/evidence-guide.md)

`monitor-calibrate` builds a pinned-model calibration from the M03 monthly
folds. `monitor-window` verifies one M06 score manifest and Parquet, evaluates
the rolling 24-hour target window, writes a JSON report and optionally replaces
the latest local [Pushgateway metric group](prometheus/ADR.md).
`monitor-drill` runs a healthy control and a tariff shock through the local
Prometheus → Alertmanager → webhook chain and fits a disposable candidate.

## Calibration and decisions

- The first 11 M03 fold windows supply the reference feature and pinned
  prediction distributions. The remaining 12 folds supply daily windows
  for calibration. Each limit is the largest measured value for its signal.
  The residual limit also has a floor at the pinned model's pooled M03
  protocol MAE. The calibration records both source hashes and the window
  that set each empirical maximum.
- PSI uses reference deciles for numeric features and reference categories
  for categorical features. Missing values and previously unseen categories
  get distinct buckets where applicable. Numeric KS compares the observed
  empirical CDF to up to 4,096 fixed quantile samples from the reference.
  The same measures cover the prediction distribution.
- Labels join by station and target hour and are visible only after their
  recorded availability. Coverage is reported immediately. MAE is evaluated
  once the entire window has matured and at least 100 labels are present.
- Drift requests retraining. The optional calendar input requests retraining
  at 30 days since the last completed training. A missing-input breach holds
  automatic retraining, and an explicit manual reason can override the hold.
  The decision records every applicable reason and a deterministic ID.
  M08 will consume the decision and own scheduling.
- A missing-rate check requires a completed score window. A missing
  day-ahead forecast batch stops feature construction before an M06 score
  exists. M08's orchestration failure path covers that case.
- The pinned artifact was fit on the calibration dataset. The daily residual
  envelope describes a replay of that artifact. Its pooled backtest MAE is
  the out-of-fold check. The empirical maximum is sensitive to the reference
  population and should be recalibrated for a new pin.

## Run locally

Run these commands from `Mlops-engineering/reference-workload` with the M05
model artifact, M02 features and M01 dataset materialized and the M06 score
already written for the issue day.

```bash
uv run --locked charging-forecast monitor-calibrate \
  --config configs/dataset-v001.yaml --release data/releases/dataset/v001 \
  --features data/features/feat-v1-dataset-v001 \
  --baseline-report ../03-baselines-evaluation/evidence/baseline-report.json \
  --out data/m07/calibration.json

uv run --locked charging-forecast monitor-window \
  --config configs/dataset-v001.yaml --release data/releases/dataset/v001 \
  --features data/features/feat-v1-dataset-v001 --issue-date 2026-12-30 \
  --as-of 2027-01-01T01:00:00Z --calibration data/m07/calibration.json \
  --out data/m07/monitor-2026-12-30.json
```

For an alert replay, put `prometheus`, `alertmanager` and `pushgateway` on
PATH. The script also recognizes the Ubuntu executable names
`prometheus-alertmanager` and `prometheus-pushgateway`. Use a new output
directory each run. The script starts and stops the local alert stack and binds
only to loopback ports 19090, 19091, 19093 and 19876.

```bash
OMP_NUM_THREADS=2 uv run --locked charging-forecast monitor-drill \
  --config configs/dataset-v001.yaml --release data/releases/dataset/v001 \
  --features data/features/feat-v1-dataset-v001 \
  --baseline-report ../03-baselines-evaluation/evidence/baseline-report.json \
  --alert-config ../07-monitoring-drift/prometheus --out data/m07/drill
```

The drill generates both score windows itself. It replays the generator's
tariff regime with an October surcharge in all six districts. The training
cutoff precedes the seven-day comparison window by the M03 embargo. The
candidate artifact, its checksum, the webhook timestamps and the paired
holdout MAEs are recorded under the output directory with a separate local
MLflow run. The drill leaves the serving pin at `model-v001`.

On a fresh checkout, run `generate` and `publish` for `dataset-v001`, then
`run-pipeline` and `pin-model` using a disposable `--models-dir`,
`--releases-dir` and local SQLite `--tracking-uri`. Run `eval-baselines`
with the resulting dataset and features. Supply the regenerated report and
the same model directories to `monitor-drill` so all three sources have
matching manifest hashes. Follow the individual CLI `--help` for parameters.

## Acceptance

1. Inject a shift, receive the alert within 30 seconds of pushing the shifted
   report, train a candidate and measure recovery on the same holdout as the pin.
2. Record a firing and a non-firing run through the actual local alert stack.
3. Record the baseline identity and measured window behind every threshold.

See the [acceptance record](evidence/m07-acceptance.md) and the [recorded threshold derivations](evidence/calibration-thresholds.json).
