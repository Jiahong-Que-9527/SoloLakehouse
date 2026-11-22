# ML Engineering

<!-- [魏征·2026-11-21] Initialize ML engineering project planning. -->

Close the loop of one machine-learning system: from problem framing and a synthetic data foundation through point-in-time features, evaluated models, a registered and releasable training pipeline, batch and online serving, drift monitoring with retraining triggers, Dagster orchestration, and a template that onboards a second model. The project targets the working skills of a mid-to-senior ML engineer and complements the domain cases: practices matured here feed back into [Taxi-in Prediction](../Fraport-adsb-intelligence/05-taxi-in-prediction/README.md), [Energy Forecasting MLOps](../gcp/05-energy-forecasting-mlops/README.md) and the [Databricks forecasting brief](../databricks/05-financial-forecasting-mlops/README.md).

**Status:** M01–M06 accepted (dataset-v001 gated; features `feat-v1-dataset-v001` with the leakage suite; baseline report over 23 folds; the gradient-boosted candidate beats both baselines — MAE 6.353 kWh vs median 7.690 and naive 9.152, full MLflow lineage; training wrapped in one idempotent pipeline with the model release `model-v001` pinned through the promotion gate, a digest-pinned training image and tested rollback; batch scoring idempotent with committed manifests and the pinned model served over HTTP in the G02 shape, shadow-compare ready). M07 is next.

## Workload and environment

- The workload is a synthetic electric-vehicle charging network: 40 stations with hourly demand over two years, station attributes, holidays and events, tariffs that change regime, and weather supplied both as realized observations and as forecasts available at issue time. A seeded generator owns the data; raw outputs stay outside Git. The [workload README](reference-workload/README.md) defines the domain and the injected regimes.
- The prediction task is fixed in M01: issue the next-day hourly demand per station at 06:00 Europe/Berlin. The issue-time availability table in the [feature contract](docs/feature-contract.md) defines what the model may see.
- Everything runs locally in WSL2 Ubuntu with Python 3.12+ and uv. MLflow runs locally per [ADR-005](../Fraport-adsb-intelligence/docs/adr/ADR-005-cloud-neutral-training-and-model-registry.md); model releases publish manifests that mirror the Gold release pattern. Dagster is the orchestrator from M08. No cloud resource is required by any planned stage; a Cloud Run serving variant is a separate, cost-gated decision.

## Projects

1. [M01 · Problem framing and data foundation](01-problem-and-data/README.md) — freeze the task contract, build the seeded generator and dataset validation.
2. [M02 · Feature pipeline and point-in-time contract](02-feature-pipeline/README.md) — implement the contract as code with leakage tests.
3. [M03 · Baselines and evaluation harness](03-baselines-evaluation/README.md) — rolling backtests, segment metrics and a deterministic report.
4. [M04 · Model development and experiment discipline](04-model-development/README.md) — gradient-boosted model with full MLflow lineage.
5. [M05 · Training pipeline, registry and release gate](05-training-pipeline-registry/README.md) — one idempotent CLI, a container image, the model release manifest and rollback.
6. [M06 · Batch scoring and online serving](06-batch-scoring-serving/README.md) — scheduled scoring plus a pinned-model API with shadow comparison.
7. [M07 · Monitoring, drift and retraining triggers](07-monitoring-drift/README.md) — residual and drift monitors wired to alerting, with a shift drill.
8. [M08 · Orchestration with Dagster](08-orchestration-dagster/README.md) — close the loop: scheduled scoring, drift-triggered retraining, observed runs.
9. [M09 · ML platform factory](09-platform-factory/README.md) — extract the template and onboard a second model.

Read the [delivery plan](docs/delivery-plan.md) for sequencing and open decisions, the [evidence guide](docs/evidence-guide.md) before recording a result, the [feature contract](docs/feature-contract.md) before implementing features, and the [model card template](docs/model-card-template.md) at every model release.

## Layout

The numbered directories own phase designs, acceptance and evidence. All source lives in one tree under `reference-workload/` — the generator, contract, features, evaluation, training, pipeline, serving, monitoring and orchestration packages — so that behavior changes stay observable across stages. Empty `.gitkeep` files mark directories reserved for implementation.

## Working loop and local checks

Work the stages in order through the loop defined in the [delivery plan](docs/delivery-plan.md): resolve the stage's open decision, implement under `reference-workload/`, run the acceptance checks, record evidence and update the stage status. Once M01 lands, the checks run like every other project:

```bash
cd Mlops-engineering/reference-workload
uv sync --locked
uv run --locked pytest
uv run --locked ruff check .
```

No check in this project touches cloud services or live sources.

## Out of scope

Distributed training, GPU and deep learning, feature-store infrastructure, streaming features, AutoML and LLM components stay out of scope for v1 (owner decision 2026-11-21). Each stage README states when its absence would need revisiting.
