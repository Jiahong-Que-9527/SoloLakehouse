# Energy Forecasting MLOps implementation plan

<!-- [房玄龄·2026-11-17] Document implementation order and acceptance evidence. -->

<!-- [GLM·2026-11-20] Replace the Vertex AI training step with the cloud-neutral path; see ADR-005. -->

**Status:** in progress — steps 1–2 landed (2026-11-22/23); steps 3–4 (evaluation, registry, gate) landed 2026-11-23; step 5 (batch scoring + rollback) open. [Project brief](../README.md) and [technical design](design.md).

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

### Step 3 — baseline vs candidate on the frozen holdout (2026-11-23)

- `evaluation.py`: the seasonal-naive baseline predicts the value at the
  same interval seven days earlier (`lag_7d_mw`), so both models score
  identical timestamps under identical missing-data rules. The candidate
  is one LightGBM regressor (CPU, fixed seed 20261123, deterministic
  single-thread fit) on the training contract's features: daily lags
  1d–7d (all from completed intervals, each carrying its source
  `interval_end` in the row) plus hour and weekday.
- **Fixture re-pin v1 → v2** (allowed by the step-1 replay rule): the v1
  waveform's only noise was a 19-interval wiggle no feature set may
  learn, which made the seasonal-naive baseline unbeatable (candidate
  MAE 0.166 vs naive 0.113 MW). v2 adds a two-week persistence anomaly
  the daily lags track: holdout MAE candidate **0.211887 MW** vs naive
  **4.896972 MW** — replays byte-identical, tolerance recorded
  (1e-6 MW). New pin `4d0e12e0…f271`, release id `g05-fixture-v2`.
- Selection on validation, then the frozen holdout comparison; the
  report records windows, seed, git SHA, library version, both models'
  MAE/RMSE/n and the replay tolerance.

### Step 4 — registry, promotion gate and manifest (2026-11-23)

- `registry.py`: the baseline registers first as version 1 (the rollback
  target); the candidate passes the gate (holdout MAE ≤ baseline) and
  registers as version 2. The manifest (`releases/model-manifest.json`)
  carries release id, input checksum, git SHA, seed, run and version
  ids, the evaluation-report checksum and both holdout metric sets.
- **Refusal drill:** a deliberately underfit candidate (one split, one
  round) on the separate `g05-fixture-losing-v1` fixture loses to the
  baseline (3.215 vs 0.113 MW); `PromotionRefused` blocks registration,
  the refusal message carries both MAEs, and the run stays queryable
  tagged `experiment_only=true` with **no registry version**.
- `pipeline.py` makes both drills repeatable:
  `python -m energy_forecast.pipeline promote` and `refuse-drill`.
- 51 tests green (11 new), ruff clean. All local, no cloud resources.

Step 5 (batch scoring into `energy_ml.prediction` with a rollback drill)
remains open.
