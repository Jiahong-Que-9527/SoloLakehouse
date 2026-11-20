# Energy Forecasting MLOps implementation plan

<!-- [房玄龄·2026-11-17] Document implementation order and acceptance evidence. -->

<!-- [GLM·2026-11-20] Replace the Vertex AI training step with the cloud-neutral path; see ADR-005. -->

**Status:** planned. [Project brief](../README.md) and [technical design](design.md).

## First delivery

Predict average MW over the next 15-minute interval. Keep the source energy in MWh and record the target conversion in the training dataset metadata.

## Implementation sequence

1. Pin a passed release or equivalent fixture. Derive average MW as interval energy divided by interval duration in hours. A 10 MWh quarter-hour yields 40 MW. Reject invalid durations. Include sufficient history for the seven-day baseline across training and holdout windows.

2. Freeze chronological train and validation windows, an untouched final evaluation window and the forecast issue time. Use only observations available at issue time. Test the boundary by supplying a future feature and verifying that dataset validation catches it.

3. Implement a seasonal-naive baseline first, then one CPU candidate with a fixed seed. Compare on identical timestamps, units and missing-data rules. Select settings on validation data, record them, then evaluate the frozen comparison on the reserved window. Record MAE, RMSE, sample count and replay tolerance.

4. Run the bounded training job as a containerized local run, or as a Cloud
   Run Job when a remote run is needed. Track runs and register the pinned
   version in MLflow, and write source SHA, dataset release, evaluation
   report and library versions into the model release manifest (ADR-005).
   Retain a deliberately losing candidate as an experiment using a separate
   fixture. If no candidate qualifies, record that result.

5. Score into BigQuery with a model version pinned per batch. Verify one prediction back to its features and training release. For rollback prepare two eligible test versions, restore the previous selection and re-score the same window. Compare batch IDs, target units and active version. Record compute costs and later residuals when actuals arrive.

## Acceptance record

A trace from a single forecast to model and data versions, a leakage check and a rejected promotion. Separate measured model quality from evidence that model delivery and rollback work. Link the run record from the project brief after execution and identify any checks still pending.
