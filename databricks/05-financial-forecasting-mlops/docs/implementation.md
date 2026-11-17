# Financial Forecasting MLOps implementation plan

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->

**Status:** planned. [Brief](../README.md) · [Design](design.md)

## First delivery

Forecast the next published USD-per-EUR observation from a pinned release. Use the next observed level as the label and USD per EUR as its unit. Use a fresh fixture or unused evaluation period reserved for this project.

## Implementation sequence

1. Write a small dated example including a weekend and repeated equal values. Define each feature by its source timestamp and availability at the forecast cutoff. Validate leakage by timestamps and source row identity; equal numeric values on consecutive dates are valid.

2. Freeze rolling development folds and one untouched final evaluation window. Keep training labels whose observation time is available by the training cutoff. Pin feature query, input snapshot, release ID, seed and library versions before evaluating the final window.

3. Compare last-value and linear baselines with one fixed candidate on identical dates. Log MAE, counts, parameters and artifacts in MLflow. Record the final comparison once; exercise rejected promotion on a separate synthetic fixture.

4. Register an eligible candidate and select its exact version for a bounded batch. Trace a prediction to model, run, release and feature version. Repeat the same batch and check unique prediction keys. Record the actual registry and compute used.

5. Use two known eligible test versions for rollback. Switch to the earlier version and reproduce its expected scores for the same snapshot. Join later actuals only after they become available, then record residuals by model version.

## Portfolio evidence

Evidence: one prediction trace, a deliberately rejected candidate and a reproducible rollback. Distinguish model delivery reliability from forecast accuracy on the measured window. Link measured results from the brief after execution.
