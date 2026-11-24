# Energy Forecasting MLOps

<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

**G05 · complete (2026-11-23): fixture v2, MW target, validation; windows + leakage test; holdout comparison — candidate 0.212 MW vs baseline 4.897; registry, gate and manifest — losing candidate refused and recorded; batch scoring into `energy_ml.prediction` with a live rollback drill (both versions coexist, prediction traced to its lineage)** · [Google Cloud roadmap](../README.md) · [Design](docs/design.md) · [Implementation plan](docs/implementation.md)

Build a traceable model delivery workflow. Use released or synthetic energy data to train a simple load-forecast baseline, register a model and serve a selected
version.

## Technical scope

MLflow tracking and model registry, containerized training jobs, Cloud Run
and Cloud Monitoring. Vertex AI is a documented migration path, not a
dependency ([ADR-005](../../Frankfurt-Airport-adsb-intelligence/docs/adr/ADR-005-cloud-neutral-training-and-model-registry.md)).

## Input and output

- **Input.** A fixed release compatible with [G04](../04-governed-energy-data-product/README.md), or an equivalent local fixture. Record the prediction target and time cutoff.
- **Output.** An evaluation report, a registered model version, a deployment record and model-serving metrics. The flagship's separate [Model Serving Integration](../../Frankfurt-Airport-adsb-intelligence/06-model-serving/README.md) can apply the same practices to the approved aviation model.

## Acceptance

1. Evaluate a baseline and candidate on the same time-ordered holdout. Document feature cutoffs and the exact training data version.
2. Deploy a pinned model version. Trace a prediction to its model, evaluation, dataset release and code revision.
3. Measure serving latency and errors. Exercise a rollback in the test environment and verify the version after rollback.

<!-- [房玄龄·2026-11-17] Document implementation order and acceptance evidence. -->

<!-- [GLM·2026-11-20] Substitute Vertex AI with MLflow and containerized training; see ADR-005. -->
