# 05 · Taxi-in Prediction

**Runtime:** Vertex AI, with local development first.

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
- Track experiments, parameters, metrics and model artifacts.
- Store model artifacts outside Git. Version them and link each to a source
  commit and training data version.

## Milestones

- **M1.** Label definition and coverage report.
- **M2.** Baselines on a time-ordered split, run locally.
- **M3.** Gradient-boosted model with experiment tracking.
- **M4.** Repeat the training as a Vertex AI job and register the model.
- **M5.** Evaluation report with error by hour, season and traffic level.

## Acceptance

- Training is reproducible from a release ID, table snapshot and commit.
- No feature uses information from after the cutoff.
- The model beats the baseline on the held-out period, or the report says it
  does not.

## Depends on

Gold releases from project 02, ingested by project 03. Training reads the
table version that matches a release ID.

## Outputs

A versioned model artifact and an evaluation report, used by project 06.
