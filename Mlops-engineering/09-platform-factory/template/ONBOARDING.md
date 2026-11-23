# Onboarding a workload from the ML delivery template

The template carries **delivery assets only** (the D07 rule): release
manifests, the entity-generic evaluation harness, the project shape and
the scoped CI fragment. Domain contracts — schemas, availability table,
quality gates, baseline definitions — stay with each workload. Upgrade
the template by extracting what a *running* workload repeats, never by
speculating.

## Inputs

| Input | Example | Notes |
|---|---|---|
| `--target` | `../district-forecast` | New, empty directory for the workload |
| `--package` | `district_forecast` | Python package name, snake_case |
| `--workload-id` | `district-forecast` | kebab-case identifier used in paths and CI |
| `--entity` / `--entity-plural` | `district` / `districts` | Entity label for the fold harness |

## Steps

1. Instantiate:
   `python ../09-platform-factory/template/instantiate.py --target <dir> --package <pkg> --workload-id <id> --entity <e> --entity-plural <es>`
2. Bring the domain code: dataset/feature builders, baselines, training
   and the CLI, all consuming `releases.py` / `evaluation.py` from the
   scaffold. Copy further delivery assets from the reference workload
   only when the new workload actually runs that stage.
3. `uv lock && uv sync` inside the target; write the tests for the
   domain contracts (leakage shift, reuse idempotence, determinism,
   gate refusal).
4. Install the CI fragment at `.github/workflows/<workload-id>.yml`
   (paths already scoped to `Mlops-engineering/<workload-id>/`).
5. Model releases use the same manifest pattern as the reference
   workload; model cards follow `Mlops-engineering/docs/model-card-template.md`.

## State and release layout (collision-free coexistence)

Everything the workload writes stays under its own directory: releases
under `<workload>/releases/`, run state under `<workload>/data/`. The
only shared touchpoint is a consumed, pinned release from another
workload, referenced by manifest SHA-256 in the derived release's
lineage — never mutated.

## Upgrade procedure

Extract into the template only after two workloads repeat a practice.
Copy the change into each onboarded workload in the same commit (they
own their code; there is no import dependency), and note it in this
file. Copier remains the considered upgrade path once the reusable
inputs stabilise.
