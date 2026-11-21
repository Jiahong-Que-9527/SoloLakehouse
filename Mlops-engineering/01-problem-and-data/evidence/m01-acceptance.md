# M01 · Acceptance evidence

All runs on WSL2 Ubuntu, 2026-11-21. Source commit `c769b7164961` (branch
`feat/full-run-m4-tooling`). Runtime versions: Python 3.13.14, uv 0.13.9,
numpy 2.5.5, pyarrow 26.0.1. Data release: `dataset-v001`, config
`configs/dataset-v001.yaml` (config SHA-256 `8c0dd791…7096` in the manifest).

## A1 · Determinism (same seed and config → identical SHA-256 per partition)

- Procedure: `uv run charging-forecast generate --config configs/dataset-v001.yaml --out data/releases/dataset/v001`, then a second generate into a separate directory; compared `sha256sum` over every file.
- First run: 32 files, 865,844 rows, 5.2 MB, 1.95 s. Second run: 2.14 s.
- Observed: all 32 partition SHA-256 digests identical; `diff` over the sorted digest lists empty.
- Also covered at test scale by `tests/test_determinism.py` (byte-identical tiny release; different seed changes bytes).

## A2 · Validation suite fails on seeded corruption, passes on the clean release

- Clean release: `uv run charging-forecast validate --config configs/dataset-v001.yaml --release data/releases/dataset/v001` → 27/27 checks PASS (schema ×7, grain uniqueness ×7, ranges ×4, continuity ×2, forecast integrity, availability ×3, regime ×3).
- Corruption cases are exercised in `tests/test_validation.py` on the tiny config (fast, deterministic): mutated tariff step date → `regime_tariff_step` FAIL; shifted forecast reference hours → `forecast_integrity` FAIL; dropped station-hours → `continuity_demand` FAIL. All three fail as required.

## A3 · Release manifest and EDA citation

- `uv run charging-forecast publish … --approver "owner (节度使大人), via session decision 2026-11-21"` → validation re-run inside the gate, then `manifest.json`, `contract.yaml`, `validation.json`, `approval.json` written and `_SUCCESS` last.
- Manifest lists every partition: 32 files, 865,844 rows, per-file size and SHA-256, release ID, seed, config SHA-256, source commit.
- Manifest digest (committed copy): `e0c8096c8233bfa2be8fbb90e9f07bd179f0d1cdaa14d333b4a0d6b741e6bfa0`. `_SUCCESS` SHA-256 `36cb4d3c…129362f25`.
- The [EDA report](eda-report.md) cites release `dataset-v001` and the manifest digest.
- Generator runtime and output size recorded in the delivery plan (M01 entry): 32 files, 865,844 rows, 5.2 MB, ~2 s per full generation.

## Checks

- `uv run --locked pytest` → 10/10 passed.
- `uv run --locked ruff check .` → clean. `uv run --locked ruff format --check .` → clean.

## Generator verification beyond the gates (found and fixed during EDA)

Three defects were found by inspecting the EDA numbers and fixed before the
release was accepted; each is covered by the current tests:

1. Event multiplier initialised to 0 (zeroed all non-event hours) — EDA showed weekend means of exactly 0.0.
2. Weekday offset +4 instead of +3 (epoch was a Thursday) — shifted all calendar factors by one day.
3. POI profiles ran at ~1.0× capacity, clipping 45 % of station-hours at the physical ceiling and diluting every regime effect — rescaled to 0.5 utilization; clip fraction now 2.5 %.

Same-seed paired A/B runs (only the regime parameter differs) verified the
elasticity (−4.24 % at full ramp, control 0.0000 %) and the heatwave timing
mask against nominal values; numbers in the [EDA report](eda-report.md).
