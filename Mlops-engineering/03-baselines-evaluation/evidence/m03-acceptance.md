# M03 · Acceptance evidence

All runs on WSL2 Ubuntu, 2026-11-22. Source commit `6489142967cdd14b3e29619282f76125ef989f11`
(branch `feat/m03-baselines-evaluation`, stacked on the M02 branch). Runtime
versions: Python 3.13.14, uv 0.13.9, numpy 2.5.5, pyarrow 26.0.1. Source data
release `dataset-v001`; feature release `feat-v1-dataset-v001` (manifest
`0d12d224c599…`) recorded in the report metadata. Protocol resolved in the
[delivery plan](../../docs/delivery-plan.md) (M03 entry, 2026-11-22).

## A1 · Fold plan: stable boundaries, embargo enforced

- Procedure: `build_folds` run twice on the frozen config — boundaries identical;
  `validate_fold` re-checked per fold; a constructed fold with
  `train_last_issue` overlapping validation raises `ValueError: embargo violation`.
- Observed: 23 monthly folds (2025-02 … 2026-12), 2025-01 skipped (0 training
  issues < the 14-issue minimum); every fold satisfies
  `train_last_issue + 1 d + embargo ≤ first validation issue`; boundaries
  month-aligned and non-overlapping. Tests: `test_folds_are_stable_and_respect_embargo`,
  `test_fold_builder_refuses_embargo_violation`, `test_fold_plan_on_the_eval_window`.

## A2 · Harness determinism: byte-identical reports

- Procedure: `uv run charging-forecast eval-baselines … --out <dir>` twice over
  `dataset-v001`; `diff -r` over both output directories.
- Observed: `baseline-report.json` and `baseline-report.md` byte-identical
  (`REPORT-BYTES-IDENTICAL`). Full run ~10.4 s.

## A3 · Baseline report over dataset-v001 (the numbers M04 must beat)

Committed report: [baseline-report.md](baseline-report.md) /
[baseline-report.json](baseline-report.json).

- Seasonal naive (demand at target hour − 168 h): pooled MAE 9.151699 kWh,
  RMSE 15.329156, sMAPE 10.587133 (n = 625,944).
- Station median (per station, by hour-of-day and weekday, fitted per fold on
  the trailing 90 days of point-in-time-readable demand at the fold's last
  training issue): pooled MAE 7.689936 kWh, RMSE 12.851236, sMAPE 8.916342
  (n = 624,144).
- Paired comparison (median vs naive, per-sample absolute-error differences,
  bootstrap 95% CI, 2,000 resamples, seed 20261122): mean difference
  −1.469961 kWh, CI [−1.494707, −1.445268] — the median baseline beats the
  naive baseline and the interval excludes zero. Worst naive segment: hour
  18:00 UTC (MAE 14.524202).
- Segment tables (by hour, station, district) are in the committed report;
  M04's model must beat these numbers under the same protocol and folds.

## Exclusion accounting (protocol: rows without a finite prediction or label)

- Total protocol rows 670,080 (698 issues × 40 stations × 24 target hours).
- All exclusions trace to exactly the three cold-start stations S038/S039/S040
  (active from 2026-10-01): label NaN 14,544 rows each (pre-active issues);
  naive predictions additionally NaN for their first post-active week
  (+168 rows each, source hour still pre-active); median predictions for the
  first post-active folds (+768 rows each, empty trailing-window cells).
  No other station or fold contributes an exclusion.

## Point-in-time discipline of the baselines

- `test_median_baseline_uses_only_point_in_time_readable_demand`: re-fitting
  the fold-2 medians from a release whose demand after the fitting horizon was
  replaced with 999.0 yields identical medians — baseline fitting reads only
  demand readable at the fold's last training issue.
- `test_seasonal_naive_equals_demand_one_week_before`: naive predictions equal
  the demand rows one week before each target hour, stamped readable at T.

## Checks

- `uv run --locked pytest` → 38/38 passed (26 through M02 + 12 M03).
- `uv run --locked ruff check .` → clean. `uv run --locked ruff format --check .` → clean.
