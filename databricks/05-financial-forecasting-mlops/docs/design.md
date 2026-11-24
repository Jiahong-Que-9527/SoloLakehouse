# Design: Financial Forecasting MLOps

**D05 · Forecasting design.** See the [Free Edition delivery](../README.md#free-edition-execution-scope) for observed results.

Forecast the next published USD-per-EUR level and keep the run, the model, and the batch scores tied to a table version and a commit. The result is a research record. It is not a trading signal.

The project [brief](../README.md) fixes the evaluation rules.

## 1. Decisions

| Topic | Decision |
|-------|----------|
| Question | Predict the level at the next published USD-per-EUR observation from a pinned Gold snapshot. |
| Claim | The report compares models on a past window. It does not estimate profit or recommend a position. |
| Cutoff | Features at date `t` use observations dated `t` and earlier. The label is the observation at the next date present in Silver, not a filled calendar day. |
| Split | Rolling time split. The last fold is the published evaluation. No random row split. |
| Baselines | Naive: predict the last observed value. Linear: one regression on the allowed lags. |
| Candidate | One gradient-boosted model on the same folds. |
| Tracking | MLflow records params, metrics, the Delta version, `release_id`, git sha, and the model artifact. |
| Registry | Unity Catalog model registry when the workspace allows it. Otherwise the workspace registry. The evidence names which one was used. |
| Promotion | A candidate is registered as the batch version only when its evaluation error is less than or equal to the naive baseline. Otherwise it stays an experiment. |
| Serving | A Lakeflow task writes batch predictions. There is no online endpoint. |
| Rollback | A later batch can be pointed at a previous registry version and must reproduce that version's scores for the same input version. |
| Monitoring | An error table joins a later actual to the prediction and stores the residual. Drift is that residual summary, not a separate service. |

## 2. Boundary

In scope: the feature query, baselines, one candidate, MLflow, the gate, batch prediction, and rollback by version.

Out of scope: order execution, portfolio logic, feature-store infrastructure, and real-time scoring. D04's feature view is the preferred read. A local fixture with the same columns is valid when the catalog is not deployed.

## 3. Architecture

```text
Pinned Gold or Silver version
          |
          v
Feature query with cutoff
          |
          v
Training run
          |
          v
MLflow experiment
          |
          +-- worse than naive --> experiment only
          |
          v
Model registry version
          |
          v
Lakeflow batch task -> prediction table
          |
          v
Residual table when the next actual is available
```

## 4. Feature contract

Row: `as_of_date`, `series_key`, `lag_1`, `lag_5`, `label`, `feature_version`, `table_version`.

`lag_1` is the latest observation at or before `as_of_date`. `label` is the following observation's value. A unit test builds a three-point series and checks that each feature uses only source rows available by the forecast cutoff.

The prediction table's grain is `(as_of_date, series_key, model_version)`. A rerun of the same version replaces those keys and does not append a second score.

## 5. Behaviour

- Training refuses to start without `table_version` and `release_id` or an explicit fixture id.
- The naive and linear runs are logged even when the candidate is promoted, so the comparison stays in the same experiment.
- The gate compares MAE on the last fold. The threshold is "no worse than naive", written in the run parameters.
- Rollback selects `model_version` as a job parameter. The new prediction rows carry that version. The previous rows for a different version remain.
- A residual row is written only when an actual exists after `as_of_date`. The monitoring task does not invent one.

## 6. Delivery and cost

Train on the sample quarter, CPU, one job run. The warehouse stops afterwards. Model artifacts stay in the MLflow store, not in git. Git holds the training code, the feature query, and the run id once evidence exists.

## 7. Acceptance

1. The feature test rejects a lookahead value. The evaluation fold starts after the training dates.
2. A worse-than-naive fixture does not become the batch version. Its MLflow run is still readable.
3. A registered version records the Delta version, the release or fixture id, and the git sha.
4. Batch scores for a pinned version match a small expected file. A second batch using the previous version is labelled with that version.
5. After one later actual is appended, the residual table has one row and the monitoring output names the model version.

## 8. Handoff

D06's ML template, when built, copies this job shape. It does not share this experiment. The aviation model keeps a separate registry.

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->

[Implementation sequence and evidence](implementation.md)
