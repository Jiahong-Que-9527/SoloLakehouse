# Financial Forecasting MLOps

<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

**D05 · Accepted on Databricks Free Edition** · [Databricks roadmap](../README.md) · [Playbook](../docs/free-edition-cli-playbook.md) · [Design](docs/design.md) · [Implementation](docs/implementation.md) · [Runbook](docs/free-edition-run.md) · [Workspace evidence](evidence/free-edition-acceptance.json)

Train and evaluate a reproducible time-series baseline, register a model version and validate a batch inference workflow.

## Technical scope

MLflow, feature engineering, Model Registry and Lakeflow Jobs.

## Input and output

- **Input.** A pinned [D01](../01-ecb-delta-lakehouse/README.md) Gold snapshot with the access conventions described in [D04](../04-unity-catalog-governance/README.md), or a compatible time-series fixture.
- **Output.** An evaluation report, tracked run and model version, and batch predictions linked to the data and feature versions.

## Acceptance

1. Use a time-ordered split. Verify that features and training labels respect the prediction and evaluation cutoffs.
2. Compare candidate and baseline on the same evaluation window. Record the Delta version, model inputs and source commit.
3. Run batch inference with a pinned model version and verify output against a small reference set. Capture job, evaluation and model registry evidence.

## Free Edition execution scope

- The CPU Serverless job evaluated a pinned Delta snapshot of 62 public ECB daily USD-per-EUR quotes from 2025 Q2 and tracked each model in MLflow.
- The 15-label final window spans 2025-06-10 through 2025-06-30. MAE in USD per EUR was **0.00513** for last value, **0.00700** for linear regression, and **0.01595** for gradient boosting. The historical candidate stayed in MLflow after missing the promotion gate.
- Two independent synthetic candidates cleared the same gate and registered as Unity Catalog model versions 1 and 2. Real job runs scored version 2, repeated it with one row per key, and rolled back to version 1 on the same Delta snapshot. A later actual produced one residual for version 1.

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->
