# M09 · Acceptance evidence

WSL2, 2026-11-23 UTC, HEAD `f342272d…3f9e`. Python 3.13, uv 0.13.9,
scikit-learn 1.9.1. The first workload's full suite (73 tests) and the
second workload's suite (22 tests) both passed with Ruff lint and format
checks clean after onboarding.

## Template

`09-platform-factory/template/` carries delivery assets only (D07 rule):
`instantiate.py` (placeholder substitution in bodies and paths, `.tmpl`
suffix stripped), `ONBOARDING.md` (inputs, steps, state layout, upgrade
procedure) and the scaffold — `releases.py` (deterministic manifests,
publish/verify), `evaluation.py` (entity-generic `HourlySeries` with the
point-in-time reads, fold plan, metric suite, paired bootstrap, report
schema), a pyproject fragment with build system, and a scoped CI
fragment. Domain contracts stayed out of the template by construction.

## Acceptance 1 · Second workload through the template

`district-forecast` was instantiated with `instantiate.py --package
district_forecast --workload-id district-forecast --entity district`,
then onboarded with its own domain code:

- dataset contract (`dataset.py`): station-hour demand aggregated to
  district-hour from the pinned `dataset-v001` (lineage by manifest
  SHA-256; `available_at` = max over contributing stations; tariff
  schedule collapsed per district with uniformity enforced);
- feature contract (`features.py`): the M02 availability table at
  district grain, verified by a leakage shift test;
- baselines (`baselines.py`) over the template harness;
- model, promotion gate and idempotent pipeline (`model.py`,
  `pipeline.py`, `cli.py`).

The regression test
`test_releases.py::test_instantiate_placeholder_substitution` freezes
the instantiate behavior (paths, bodies, suffix stripping).

**Measured onboarding effort:** 14:48 UTC (template authoring start) →
17:08 UTC (acceptance checks green) ≈ **2 h 20 m wall clock**, of which
the template extraction itself was roughly half; the district-forecast
domain code plus its 22 tests is the other half. The scripted
instantiate step is seconds; every deviation is in the friction list
below. This mirrors D07's measured onboarding (≈2 h).

Full-scale delivery on the real pinned release (729 issue days × 6
districts × 24 target hours): the pipeline ran end to end in **54 s**
and published `model-district-2a1a4b7a6bd8eb34` — pooled protocol MAE
**22.338 kWh** (RMSE 36.157, sMAPE 4.59, n = 100,368) over 23 monthly
folds (2025-01 skipped), strictly beating both committed baselines
(seasonal-naive 30.980, district median 33.629). The promotion gate
passed and the release manifest carries full lineage; the model card
ships next to the manifest.

## Acceptance 2 · No collision, first workload untouched

- The full-scale rerun reused every step in **0.86 s** (dataset,
  features, baselines, training, publish) with identical bytes; unit
  tests assert the same reuse-by-content discipline on the fixture.
- The reference workload's releases and artifacts are unchanged:
  `reference-workload/releases/models/` still holds only `model-v001`,
  `model-v002` and `pinned.json`; its 73-test suite passes untouched.
- The two workloads share nothing but the consumed release, referenced
  by manifest digest; releases, scoring state and model artifacts live
  in each workload's own directory.

## Acceptance 3 · Friction list → template changes

Gaps found during onboarding and fixed in the template the same session:

1. `instantiate.py` crashed on its final print (str + Path
   concatenation) — fixed.
2. The `.tmpl` suffix was not stripped from instantiated paths — fixed
   and regression-tested.
3. The scaffold pyproject lacked a `[build-system]` section, so the
   package did not install — fixed in the template.
4. `evaluation.py` lacked a `REPORT_SCHEMA_VERSION` constant the
   harness callers need — added (`eval-report-v1`).

Accepted limitations (recorded, not templated): the second workload
re-implements `DistrictDemand` on top of the template's `HourlySeries`
rather than importing it (workloads own their code); monitoring and
serving stay with the reference workload and were deliberately not
templated for M09.

## Checks

- `district-forecast`: 22 tests passed (fixture covers aggregation
  semantics, tariff uniformity refusal, leakage shift, forecast
  boundary, feature determinism, baseline report determinism, fold
  skipping, gate refusal, full-pipeline reuse, instantiate regression);
  Ruff clean.
- `reference-workload`: 73 tests passed; Ruff clean.
- CI fragment installed at `.github/workflows/district-forecast.yml`,
  scoped to `Mlops-engineering/district-forecast/**`.
