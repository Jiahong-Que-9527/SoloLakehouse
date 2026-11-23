# 05 · Taxi-in Prediction

<!-- [GLM·2026-11-20] Replace the Vertex AI runtime with the cloud-neutral MLflow path; see docs/adr/ADR-005. -->

**Runtime:** Local training first, packaged as a container; MLflow for experiment tracking and the model registry ([ADR-005](../docs/adr/ADR-005-cloud-neutral-training-and-model-registry.md)).

Train and evaluate a model that predicts taxi-in time for arrivals at `EDDF`.
Start with a simple baseline and add complexity only when it improves a
measured result.

## Important caveat

Taxi-in labels derive from ADS-B state vectors. They are proxy labels, not
airport ground truth. Report label coverage and definition with every result.

## Scope

- Define the target: start and end events, and the rules for edge cases.
- Use the per-flight features from the Gold release, with a strict prediction
  cutoff. Features and labels are built in project 02.
- Use a time-ordered split. Never shuffle across time.
- Establish baselines first (historical mean or median by condition), then a
  gradient-boosted model.
- Track experiments, parameters, metrics and model artifacts in MLflow.
- Store model artifacts outside Git. Version them and link each to a source
  commit and training data version.

## Milestones

- **M1.** Label definition and coverage report.
- **M2.** Baselines on a time-ordered split, run locally.
- **M3.** Gradient-boosted model with experiment tracking.
- **M4.** Repeat the training as a containerized job, register the model version in MLflow and publish its release manifest (ADR-005).
- **M5.** Evaluation report with error by hour, season and traffic level.

## Acceptance

- Training is reproducible from a release ID, table snapshot and commit.
- No feature uses information from after the cutoff.
- The model beats the baseline on the held-out period, or the report says it
  does not.

## Depends on

Training pins the Gold label-table version and release ID from the
[project 04 lakehouse handoff](../04-aviation-lakehouse/README.md#handoff-to-taxi-in-prediction).
Predictive features require a separate point-in-time source with documented
event and availability timestamps. The Geometry v2 table supplies proxy
labels and join metadata.

## Outputs

A versioned model artifact and an evaluation report, used by project 06.
