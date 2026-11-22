# M04 · Acceptance evidence

All runs on WSL2 Ubuntu, 2026-11-22. Source commit `8bb3484` (`origin/main`,
the M03 merge; the M04 branch is cut from it and the reports were generated
from this working tree before the stage commit). Runtime: Python 3.13,
scikit-learn 1.9.1, numpy 2.5.5, MLflow 3.18.0 (local sqlite tracking store,
`mlruns.db`, gitignored). Data release `dataset-v001`; feature release
`feat-v1-dataset-v001`. Decisions resolved in the
[delivery plan](../../docs/delivery-plan.md) (M04 entry, 2026-11-22).

## A1 · The candidate beats both baselines under the M03 protocol

Committed report: [model-report.md](model-report.md) /
[model-report.json](model-report.json). The seasonal-naive and station-median
columns are recomputed inside the same protocol run from the same demand
table and fold plan, and match the committed M03 report to the sixth decimal.

| Model | MAE (kWh) | RMSE | sMAPE | n |
|---|---|---|---|---|
| **Model (selected config)** | **6.352612** | 9.837125 | 8.450599 | 626,376 |
| Station median (M03) | 7.689936 | 12.851236 | 8.916342 | 624,144 |
| Seasonal naive (M03, gate) | 9.151699 | 15.329156 | 10.587133 | 625,944 |

- Gate: model beats seasonal-naive — **yes** (acceptance 1). It also beats
  the stronger station-median baseline.
- Paired comparisons (per-sample |err| differences, 2,000-resample bootstrap,
  seed 20261122): model vs naive −2.799631 kWh, 95% CI
  [−2.824427, −2.774531]; model vs median −1.334329 kWh, 95% CI
  [−1.353366, −1.315610]. Both intervals exclude zero.
- Per fold: the model beats the station median on **all 23 folds** (the
  per-fold MAE table is in the committed report). Worst fold 2025-04
  (least training history): model 9.048 vs median 10.110 vs naive 10.918.

## A2 · MLflow lineage on every run

- Every run is tracked to the local MLflow store (experiment
  `charging-forecast-m04`) with the full tag schema — `stage`, `run_kind`,
  `data_release_id` (`dataset-v001`), `feature_release_id`
  (`feat-v1-dataset-v001`), `git_sha`, `fold_plan` (embargo, minimum train
  issues, fold count, skipped months) — plus params, metrics and, on the
  protocol run, the committed report artifacts. Verified programmatically
  over all tracked runs: none missing a tag
  (`test_every_mlflow_run_carries_the_lineage_schema` covers the same
  assertions on a fixture store).
- Accepted run: grid runs `2be65878…`…`d4e1e5c7…` (8 configs) and protocol
  run `3682eefa25e346f5b2eb7b8569397021`.
- Defect found and fixed during the stage: the report's `source_commit`
  read the repo commit before the output directory existed and recorded
  `unknown`; the call now happens after the directory is created, so the
  report and the MLflow tags carry the real commit.

## A3 · Segment tables: no silent regression

Against the station median (the stronger baseline), from the committed
report:

- **All 6 districts improve**: D1 −1.424, D2 −1.429, D3 −0.929, D4 −1.631,
  D5 −1.347, D6 −1.128 kWh MAE.
- **All 40 stations improve** (or tie at worst): the smallest gain is
  −0.058 kWh at S040 (a 2026-10 cold-start station), the largest −2.673 kWh
  at S034. No segment regresses (acceptance 3).
- By hour, the model wins every hour; the hardest hour is 18:00 UTC
  (model MAE 9.741), mirroring the M03 evening peak.

## Selection discipline

- Internal split: train on issues ≤ 2026-08-31 (539,904 labeled rows),
  validate on September 2026 (26,640 rows); the protocol folds never touch
  the selection split.
- Fixed seeded grid (8 configs, learning_rate × max_leaf_nodes ×
  min_samples_leaf), 300 iterations, early stopping off, one OpenMP thread;
  the winner is lr 0.1 / 63 leaves / min-samples-leaf 40 with validation
  MAE 6.086714 (full grid table in the report).
- Training rows come only through `features.load_training_features` (the
  contract's read path, batched to one scan with the same
  `available_at == T` rule the per-fold leakage check verifies); rows with
  unreadable labels are excluded on both sides of every comparison.

## Determinism and tests

- `test_report_bytes_are_identical_across_runs`: two full
  `run_model_training` runs over the fixture produce byte-identical
  `model-report.json` / `model-report.md` (no wall-clock values, no MLflow
  run IDs in the report). Confirmed at full scale: two complete runs over
  `dataset-v001` produced identical report bytes
  (`REPORT-BYTES-IDENTICAL`).
- `test_predictions_deterministic_given_seed`: two fits on identical data
  predict identically (thread count pinned via `OMP_NUM_THREADS=1` before
  sklearn loads — the recorded M03 risk about multithreaded
  nondeterminism is void for this implementation).
- `test_protocol_matches_the_m03_baseline_report`: the baselines recomputed
  inside the protocol equal the M03 harness's report and fold plan.
- Full suite: 46/46 passed; `ruff check` and `ruff format --check` clean.
