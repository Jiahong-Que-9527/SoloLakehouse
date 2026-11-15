# Energy Forecasting MLOps

<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

**G05 · Planned** · [Google Cloud roadmap](../README.md) · [Design](docs/design.md)

Build a traceable model delivery workflow. Use released or synthetic energy data to train a simple load-forecast baseline, register a model and serve a selected
version.

## Technical scope

Vertex AI training, Model Registry, Cloud Run and Cloud Monitoring.

## Input and output

- **Input.** A fixed release compatible with [G04](../04-governed-energy-data-product/README.md), or an equivalent local fixture. Record the prediction target and time cutoff.
- **Output.** An evaluation report, a registered model version, a deployment record and model-serving metrics. The flagship's separate [Model Serving Integration](../../Fraport-adsb-intelligence/06-model-serving/README.md) can apply the same practices to the approved aviation model.

## Acceptance

1. Evaluate a baseline and candidate on the same time-ordered holdout. Document feature cutoffs and the exact training data version.
2. Deploy a pinned model version. Trace a prediction to its model, evaluation, dataset release and code revision.
3. Measure serving latency and errors. Exercise a rollback in the test environment and verify the version after rollback.
