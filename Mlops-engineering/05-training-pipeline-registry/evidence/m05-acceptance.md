# M05 · Acceptance evidence

All runs on WSL2 Ubuntu, 2026-11-22. Source commit `7842ab6` (the working
tree's HEAD; the reports and manifests were generated before the stage
commit, mirroring the M04 evidence). Runtime: Python 3.13, scikit-learn 1.9.1,
numpy 2.5.5, MLflow 3.18.0 (local sqlite tracking store and model registry,
`mlruns.db`, gitignored). Data release `dataset-v001`; feature release
`feat-v1-dataset-v001`; model release `model-v001`. Decisions resolved in the
[delivery plan](../../docs/delivery-plan.md) (M05 entry, 2026-11-22).

## A1 · The pipeline is idempotent — checked, not claimed (acceptance 1)

`run-pipeline` executed twice over the same inputs
(`data/releases/dataset/v001`, `data/features/feat-v1-dataset-v001`). The
second run reported every step reused (validate/features/train/register/
publish), the committed manifest bytes were identical
(`MANIFEST-BYTES-IDENTICAL`) and the artifact checksum was unchanged
(`ARTIFACT-BYTES-IDENTICAL`). The first full training of the chain had been
interrupted after the report was written; the rerun reused that report
instead of retraining — the identity check (dataset manifest SHA, feature
manifest SHA, git commit, max_iter, seed, grid, selection split) is content,
not timestamps.

- First full run: model MAE **6.352612** kWh — identical to the sixth decimal
  to the committed M04 report (same data, seed, grid and protocol; only
  `source_commit` moved to the current HEAD).
- Train wall time on the rerun: full reuse, no retraining.

**Incident the gate caught.** The first chain attempt hit the manifest
collision guard — for a real reason. A second agent session sharing this
working tree checked out its own branch (`chore/gcp-cost-housekeeping`,
commit `c6f457a`) between two pipeline runs; `git_commit()` — part of the
train identity — saw the different HEAD, the identity no longer matched the
existing report, the pipeline retrained (producing byte-identical metrics,
MAE 6.352612 again), and `step_publish` correctly refused to write different
content under the immutable release ID `model-v001`. After the checkout
returned to this branch, a rebuilt manifest diffed empty against the
published one. The incident validated the collision guard beyond its unit
test and is an operational hazard of sharing one working tree across
concurrent agent sessions, not a code defect.

## A2 · Determinism (acceptance 2)

- `test_release_artifact_bytes_are_deterministic`: two fits of the same
  config over the same rows serialize to byte-identical `model.joblib`
  (sha256 equal), so the committed artifact checksum is reproducible.
- Real-data confirmation: the interrupted run's report and the fresh
  run's report agree to the sixth decimal on every metric (MAE 6.352612,
  RMSE 9.837125), and the artifact refit from the selected config is
  checksum-identical across runs (`ARTIFACT-BYTES-IDENTICAL`,
  sha256 `357c4fbff26787e2…`, 1,003,959 bytes).

## A3 · Registry lineage and the committed manifest

`releases/models/model-v001/manifest.json` (committed):

- `model_release_id` `model-v001`, `kind` `model`, registry model
  `charging_demand_forecast`, MLflow version `1`, source run `f5c32881…`.
- `source_commit` `7842ab6…`, `data_release_id` `dataset-v001`
  (+ dataset manifest SHA-256), `feature_release_id` `feat-v1-dataset-v001`
  (+ feature manifest SHA-256), `model_config` (selected grid winner),
  `max_iter` 300, `seed` 20261122.
- Protocol metrics in the manifest: model MAE **6.352612**, seasonal-naive
  **9.151699**, station median **7.689936**; fold plan (23 folds, embargo 1 d).
- `artifact.sha256` = the checksum of `data/models/model-v001/model.joblib`
  (the artifact itself stays outside Git, the local stand-in for ADR-005's
  versioned bucket).
- Every registry version carries the tag schema: `model_release_id`,
  `data_release_id`, `feature_release_id`, `git_sha`, `release_stage`.

## A4 · Promotion gate, pin and rollback drill (acceptance 3)

- **First pin.** `pin-model --model-release-id model-v001` passed the gate by
  beating both committed M03 baselines (model 6.352612 vs seasonal-naive
  9.151699 and station median 7.689936). `releases/models/pinned.json`
  records the pinned release ID and the manifest SHA-256
  (`c31adfd530a70d2e…`).
- **Verification.** `verify-pin` re-checked the artifact checksum against the
  manifest and re-scored the fixed verification day **2026-12-30**: 960
  predictions (40 stations × 24 h), `predictions_sha256` `64a8ef50282f40ca…`,
  written to `data/reports/verify/verify-model-v001-2026-12-30.json`.
- **Failed promotion.** A second candidate `model-v002` (max_iter 250) was
  trained (protocol MAE **6.377663** — worse than the 300-iteration pin,
  as expected), registered as version 2 and published; `pin-model` refused
  it: `promotion refused: model-v002 MAE 6.377663 is not better than pinned
  release model-v001 MAE 6.352612; the pin stays` (exit 1, refusal recorded
  in the chain log). The pin stayed on `model-v001`.
- **Post-refusal verification.** `verify-pin` after the refusal returned the
  same `predictions_sha256` `64a8ef50282f40ca…` — the pinned model and its
  outputs are untouched by the refused candidate.
- **Rollback semantics** (unit-tested end to end on the fixture):
  promote a better candidate → the previous pin is demoted to
  `release_stage=registered`, not deleted; re-pinning it is a rollback — the
  gate does not apply to a demoted former pin, and `verify-pin` reproduces
  the earlier prediction bytes exactly.

## Defects found and fixed during the stage

1. **skops trust**: MLflow 3.18 serializes sklearn models with skops and
   refuses `HistGradientBoostingRegressor`'s private `TreePredictor` unless
   it is explicitly trusted. `step_register` now passes
   `skops_trusted_types=["sklearn.ensemble._hist_gradient_boosting.
   predictor.TreePredictor"]` — our own fit output, the only flagged type.
2. **Register order**: the first implementation searched the registry for the
   version by its `model_release_id` tag immediately after `log_model`
   created it — before the tag was set, so the first registration always
   failed. `step_register` now takes the version number from `log_model`'s
   returned `ModelInfo` and sets the tags on that version directly.

## Test budgets (why the fixture is the size it is)

The M05 tests need the model to beat the station-median baseline inside the
promotion gate. On a one-year slice of the synthetic fixture the global model
(the fixture has no station-identity features) cannot — the probe measured
protocol MAE 9.498 (200 iter) and 9.367 (300 iter) vs median 9.014: the 2026
regimes the model exploits (heatwave, tariff-ramp tail, late activations) are
missing. With the full two-year window the picture matches the real data:
small grid (300 iter) reaches **8.334** vs median 8.694 and naive 10.355, the
M04 grid selects `lr 0.1 / 63 leaves / min_samples_leaf 40` — the same winner
as on the real dataset — and reaches **8.105**, strictly better. The tests use
exactly this ladder: `model-v001` (small grid) pins first; `model-v002`
(M04 grid) promotes; the rollback re-pins `model-v001`; a forged `model-v003`
manifest (v001 MAE + 0.1, no registry version) is refused by the gate.

## Tests and lint

- Full suite: **51/51 passed** (`pytest -q`, 46 prior + 5 new), `ruff check`
  and `ruff format --check` clean.
- New in M05 (`tests/test_pipeline.py`, 5 tests): artifact byte
  determinism, run-twice idempotence (registry version and manifest bytes
  stable), manifest lineage, manifest-collision refusal, and the
  pin/gate/rollback/refusal drill.
- CI: the scoped workflow gains the `image` job — `docker build` of the
  pinned-base training image and `docker run --rm … --version` smoke test.
  Local `docker` is unavailable in this environment (binary I/O error), so
  the image check runs in CI only.
