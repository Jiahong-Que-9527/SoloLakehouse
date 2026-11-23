# Energy Forecasting MLOps implementation plan

<!-- [房玄龄·2026-11-17] Document implementation order and acceptance evidence. -->

<!-- [GLM·2026-11-20] Replace the Vertex AI training step with the cloud-neutral path; see ADR-005. -->

**Status:** in progress — step 1 (pinned fixture, average-MW target, dataset validation) landed 2026-11-22; step 2 (window freeze, issue-time cutoff, leakage test) landed 2026-11-23; steps 3–5 open. [Project brief](../README.md) and [technical design](design.md).

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

## Step records

### Step 1 — pinned fixture, average-MW target, dataset validation (2026-11-22)

Landed in [PR #253](https://github.com/Jiahong-Que-9527/SoloLakehouse/pull/253):

- Pinned synthetic release `g05-fixture-v1` (status `passed`) in the G01
  `metric_observation` schema: four aligned weeks from the 2026-06-08
  anchor, so the seven-day seasonal lag exists for every interval from
  day 8 onward. Values are a pure integer-arithmetic waveform (no libm,
  no RNG) and the build is pinned by canonical checksum `f4d1f4d8…` —
  replays are byte-identical.
- Target conversion `load_mw = value (MWh) / duration (hours)`, recorded
  in the dataset metadata: 10 MWh over a quarter-hour yields 40 MW.
  Invalid durations, non-finite values and negative energy are refused.
- Dataset build refuses a release without an id, a non-`passed` status,
  duplicate business keys, and a grid with gaps or non-uniform interval
  lengths; metadata records the target definition, window, row count and
  input checksum.
- 27 tests green, ruff clean, test-only CI workflow on the project paths.
  All local, no cloud resources touched.

### Step 2 — window freeze, issue-time cutoff, leakage test (2026-11-23)

- `splits.freeze_windows` freezes the chronological split for the pinned
  fixture: train = the window through the week before last, validation =
  the third week, holdout = the last contiguous week (untouched by any
  selection, recorded as such in the spec). The spec carries the design's
  forecast issue rule verbatim: features for an interval may only use
  observations whose `interval_end` is at or before that interval's
  start. The validator refuses unordered, non-contiguous or
  out-of-window specs and a validation window that starts before the
  seven-day seasonal lag is readable from the train window.
- `features.build_features` builds one row per interval whose lag is
  readable at the issue time; the 672 rows of the first week are
  excluded and counted, never back-filled (4-week fixture → 2,016
  feature rows over train/validation/holdout).
- `features.validate_features` re-derives the contract from the rows
  and refuses: a feature sourced from an observation ending after the
  row's issue time (the acceptance boundary — a supplied future feature
  is caught by `no_lookahead`), a lag value differing from the dataset
  at the seven-day interval, labels differing from the training rows,
  and calendar fields not derived from `interval_start`.
- 40 tests green (18 new), ruff clean. All local, no cloud resources.

Steps 3–5 (baseline vs candidate, MLflow registry + promotion gate,
batch scoring + rollback) remain open.
