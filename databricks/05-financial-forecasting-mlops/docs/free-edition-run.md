# Run D05 on Databricks Free Edition

D05 trains on a frozen 62-observation ECB reference-rate fixture for 2025 Q2. The [fixture](../fixtures/ecb_2025q2.json) records the source URL and the download's SHA-256. The training job writes a separate Delta snapshot and reads back its exact version. D01's ten observations and D04's single-row feature view demonstrate their respective contracts. D05 uses the ECB quarter for held-out model evaluation.

## Run the bundle

Use an existing Databricks CLI profile authorized for Workspace and Jobs. Deploy into a fresh D05 schema for each independent training exercise.

```sh
schema="ecb_d05_$(date -u +%Y%m%d_%H%M%S)"
vars="schema=$schema,git_sha=$(git rev-parse HEAD)"
databricks bundle validate --strict -p slh-free -t dev --var "$vars"
databricks bundle deploy -p slh-free -t dev --var "$vars"
databricks bundle run d05_forecasting -p slh-free -t dev --var "$vars" \
  --params phase=train
```

Training records the last-value baseline, linear regression and one fixed gradient-boosted candidate in MLflow. Expanding windows begin after 24 and 32 labeled examples for development and after 42 for final evaluation. All models use the same label dates at each fold. The promotion rule uses final-window MAE in USD per EUR and requires the candidate to meet or beat the last-value baseline.

The job trains two additional models on distinct synthetic releases for the registry and rollback exercise. An independent synthetic regime tests the rejected path. These fixtures keep the lifecycle checks reproducible across different outcomes on historical FX.

## Score, replay and monitor

Read both exact versions in `rollback_versions` from the training task's output. Substitute those versions for the two placeholders below. Both models score the same immutable Delta input.

```sh
databricks bundle run d05_forecasting -p slh-free -t dev --var "$vars" \
  --params phase=score,model_version=NEW_VERSION
databricks bundle run d05_forecasting -p slh-free -t dev --var "$vars" \
  --params phase=score,model_version=NEW_VERSION
databricks bundle run d05_forecasting -p slh-free -t dev --var "$vars" \
  --params phase=score,model_version=OLD_VERSION
databricks bundle run d05_forecasting -p slh-free -t dev --var "$vars" \
  --params phase=monitor,model_version=OLD_VERSION
```

The reference scores are derived independently from the two alternating training series. Every boosted stump corrects 20% of the remaining distance from the balanced training mean to the matching target. After 20 stages, the expected score is `target + (mean - target) * 0.8 ** 20`. The score task compares registry predictions against [these values](../fixtures/rollback_reference.json). A Delta merge keeps one prediction per cutoff, series and model version. The monitoring task makes one later observation available and persists the signed residual for the selected version.
