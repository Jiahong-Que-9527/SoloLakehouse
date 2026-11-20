# Design: Energy Forecasting MLOps

**G05 · Design only.** No application code in this directory yet.

Train, evaluate, register, and batch-score one forecasting model, and refuse to register a model that loses to the baseline. The project proves the lifecycle. It does not prove forecast skill.

The project [brief](../README.md) fixes the first target.

## 1. Decisions

| Topic | Decision |
|-------|----------|
| Target | Next 15-minute average load in MW for `DE`, derived from G01 interval energy (`actual_load_mwh`) divided by its duration in hours. Price forecasting is the same pipeline with a different label once `energy-prices` is a passed release. |
| Split | Time ordered. The holdout is the last contiguous part of the window. Rows are not shuffled. |
| Cutoff | Features for an interval use only observations whose `interval_end` is at or before that interval's start. |
| Baseline | Seasonal naive: the value at the same interval seven days earlier. If the v1 window is one week, the fixture is extended with a second week so the baseline exists. |
| Candidate | One gradient-boosted model, CPU, fixed seed. CatBoost or LightGBM. The library choice is recorded in the run, not left open at release time. |
| Promotion | Register only when holdout MAE is less than or equal to the baseline MAE. A failed candidate remains an experiment and does not become the default version. |
| Serving | Batch prediction to a BigQuery table. No continuously running online endpoint. |
| Rollback demo | One Cloud Run revision can score a pinned model version for a short check, with minimum instances at zero. The batch table is the serving record. |
| Reproducibility | A rerun with the same release id, git sha, and seed must match recorded MAE within an absolute tolerance written in the evaluation report. |

## 2. Boundary

In scope: dataset build, baseline, one candidate, a containerized training
pipeline, MLflow tracking and registry, the promotion gate, batch prediction,
and a rollback to the previous registered version. The trial account cannot
use Vertex AI; the substitution and its migration path are recorded in
[ADR-005](../../Fraport-adsb-intelligence/docs/adr/ADR-005-cloud-neutral-training-and-model-registry.md).

Out of scope: weather ingestion, hyperparameter search, feature store, online A/B traffic, and any claim that the model should be used operationally. The aviation serving project keeps its own contract. It may copy this promotion rule. It does not call this pipeline.

## 3. Architecture

```text
Passed G04 release, or a fixture with a release id
          |
          v
Feature table   cutoff enforced in the query
          |
          v
Training pipeline (container, run on demand)
  train baseline -> train candidate -> evaluate -> gate
          |
          +-- fail --> experiment only
          |
          v
MLflow Model Registry      version, params, release id, git sha, metrics
          |
          v
Batch prediction job -> BigQuery energy_ml.prediction
          |
          v
Rollback selects the previous registry version and writes a new batch
```

## 4. Training contract

Training row: `interval_start`, label `load_mw`, lag features from completed intervals only, and calendar fields derived from `interval_start` (hour, day of week). No column may contain a value observed after the cutoff.

The pipeline parameters are `release_id`, `git_sha`, `seed`, `holdout_start`, and the model library version. The evaluation report stores MAE and RMSE for baseline and candidate, the holdout window, and the row count.

`energy_ml.prediction` stores `interval_start`, `predicted_mw`, `model_version`, `release_id`, and `predicted_at`. A second batch for the same version and interval replaces those keys.

## 5. Behaviour

- The pipeline refuses a release whose G04 status is not `passed`, and refuses a fixture that does not name a release id.
- The candidate registers only through the gate. A manual upload to the registry is outside the supported path.
- Rollback does not delete the failed version. It sets the previous version as the one the batch job reads, reruns the batch, and records both version ids.
- Monitoring for v1 is the batch error against a later holdout: MAE and residual mean. There is no always-on drift service. Prediction drift and residual drift are columns in that report, computed when a later actual is available.

## 6. Delivery and cost

Training uses the small fixture and CPU. The pipeline runs on demand. The online revision is deployed only for the rollback demonstration and is left with no traffic afterwards. The evaluation report records the training run id and the observed training cost.

## 7. Acceptance

1. The same release, config, and seed produce an evaluation report whose MAE matches the stored report within the stated tolerance. The holdout is after the training range. A feature built from a future interval fails the dataset check.
2. A candidate with a deliberately worse fixture does not gain a registry version. The experiment run is still queryable.
3. A prediction row traces to model version, evaluation, release id, and git sha.
4. After rollback, a new batch is tagged with the previous version. Record both version ids and the batch job ids.

## 8. Handoff

G06 may template the pipeline trigger later. This project keeps its own registry and its own prediction table.

<!-- [房玄龄·2026-11-17] Document implementation order and acceptance evidence. -->

[Implementation sequence and evidence](implementation.md)
