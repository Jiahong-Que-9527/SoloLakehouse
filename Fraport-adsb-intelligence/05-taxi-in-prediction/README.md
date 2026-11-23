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
- Train from the pinned Parquet dataset and feature manifest produced by
  project 04. The Geometry v2 release from project 02 supplies proxy labels.
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

- Training is reproducible from the label release ID, label and training
  manifest hashes, source commit and recorded split dates.
- The feature manifest gives the prediction cutoff, timestamp provenance and
  passed leakage checks for the rows used in training.
- The model beats the baseline on the held-out period, or the report says it
  does not.

## Depends on

The [project 04 feature handoff](../04-aviation-lakehouse/README.md#first-delivery)
supplies the versioned local training artifact. Record label coverage,
matching losses and any simulated historical availability when reporting
baseline results in MLflow.

## Outputs

A versioned model artifact and an evaluation report, used by project 06.
