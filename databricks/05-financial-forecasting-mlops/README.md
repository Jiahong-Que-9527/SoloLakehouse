# Financial Forecasting MLOps

<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

**D05 · Planned (Databricks Free Edition · Serverless + MLflow + DABs CLI)** · [Databricks roadmap](../README.md) · [Playbook](../docs/free-edition-cli-playbook.md) · [Design](docs/design.md) · [Implementation plan](docs/implementation.md)

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

- Runs as a CPU Serverless job via **Databricks CLI** (`databricks bundle run`) reading a pinned D01 Delta version, tracking naive, linear, and gradient-boosted runs in MLflow, and recording which registry (Unity Catalog or workspace registry) Free Edition supports.
- Batch scoring and `model_version` rollback are triggered via parameterized bundle runs without online serving endpoints. See [Free Edition & CLI Playbook](../docs/free-edition-cli-playbook.md).

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->
