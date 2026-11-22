# M02 · Acceptance evidence

All runs on WSL2 Ubuntu, 2026-11-22. Source commit `047327de775d9d093d7669c31f0010d65a6417f7`
(branch `feat/m02-feature-pipeline`). Runtime versions: Python 3.13.14, uv 0.13.9,
numpy 2.5.5, pyarrow 26.0.1. Source data release: `dataset-v001` (config
`configs/dataset-v001.yaml`), consumed through its committed manifest. Feature
release: `feat-v1-dataset-v001`, schema `charging-features-v1`, 21 columns per
the [feature contract](../../docs/feature-contract.md) v1.

## A1 · Shift test: delaying availability makes rows unreadable, advancing changes nothing

- Procedure (pytest suite, `tests/test_leakage.py`): shift every feature row's
  `available_at` one hour later in the materialized Parquet, then read through
  `load_issue_features` — the loader returns 0 rows; the raw Parquet still
  holds the rows, so bypassing the loader would leak them.
- Source-level delay (+1 h on the demand table's `available_at`): rebuilding
  the issue turns `demand_latest` unreadable (NaN) while earlier-anchored
  columns keep their exact values, because lag windows are fixed clock ranges.
- Source-level advance (−1 h): the rebuilt feature table is identical to the
  clean build on every column except the stamps themselves.
- Observed: all three behaviors pass (`test_shift_delay_makes_rows_unreadable_to_the_loader`,
  `test_source_delay_turns_affected_lags_unreadable`, `test_source_advance_changes_no_feature_value`).

## A2 · Duplicate materialization: byte-identical Parquet and manifests

- Procedure: `uv run charging-forecast features-build … --out <dir>` twice from
  the same release and tree; `sha256sum` over every file in both directories.
- Tiny-release check: `test_duplicate_materialization_is_byte_identical` —
  manifests equal, every partition byte-identical.
- Real-release check: two full-range builds into `data/features/` produce
  identical digests for all 24 partitions and `manifest.json`
  (`DUPLICATE-BUILD-IDENTICAL`). Note: the manifest carries `source_commit`
  by design (M01 lineage pattern); a build outside a Git repository records
  `unknown`, so the byte-identity comparison is defined for builds from the
  same source tree.

## A3 · Per-fold automated leak check over every fold

- Procedure: `uv run charging-forecast features-check-leaks --features
  data/features/feat-v1-dataset-v001 --issue-start 2025-01-01 --issue-end 2026-12-30`.
- Observed: 729/729 folds PASS — every target-window row is stamped exactly at
  its issue time `T`, no row stamped after `T`, every target hour strictly
  future, and the stamp-selected and window-selected row sets agree per fold.
  The tamper tests (`test_fold_check_passes_clean_features_and_detects_tampering`,
  `test_fold_check_flags_past_targets`) confirm the check fails loudly on a
  re-stamped or mis-windowed row.

## Full-range materialization on dataset-v001

- Command: `uv run charging-forecast features-build --config configs/dataset-v001.yaml
  --release data/releases/dataset/v001 --issue-start 2025-01-01 --issue-end
  2026-12-30 --out data/features/feat-v1-dataset-v001`
- Observed: 729 issues, 653,904 rows, 24 monthly partitions, 4.4 s. Row count
  reconciles exactly with the station timeline: 37 readable stations × 24
  hours per issue until 2026-09-30, 40 from 2026-10-01 (the cold-start trio),
  plus the loader's history read path (e.g. issue 2026-04-01 reads 404,928
  rows, all stamped at or before T).
- Manifest digest (committed copy at `releases/features/v001/manifest.json`):
  `0d12d224c59928b85660d797c7a8a3af89702642f3cc7b288148321bd7f4f946`.
- DST spot checks through the loader: issue stamps are 05:00Z through
  2025-03-29, 04:00Z from 2025-03-30, 04:00Z through 2025-10-25, 05:00Z from
  2025-10-26 — the 06:00 Europe/Berlin rule holds across both transitions.

## Forecast integrity beyond the gates

The forecast-reference test initially passed its join despite shifted
reference hours, because other issues' rows filled the gap. The builder now
additionally enforces the day-ahead issue convention: a readable forecast row
for reference hour `h` must carry the issue timestamp 06:00 Europe/Berlin on
the day before `h`'s date. Rows joined under a wrong reference time violate
the convention and fail the build (`test_forecast_with_wrong_reference_time_fails_the_build`).
The rule is written into the feature contract's leakage-test section.

## Checks

- `uv run --locked pytest` → 26/26 passed (10 M01 + 16 M02).
- `uv run --locked ruff check .` → clean. `uv run --locked ruff format --check .` → clean.
