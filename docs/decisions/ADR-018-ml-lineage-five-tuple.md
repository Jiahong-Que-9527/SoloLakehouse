# ADR-018: ML Lineage Five-Tuple

**Status:** Accepted  
**Date:** 2026-08-02  
**Version:** v2.8 (E1)

## Context

v2.8 requires every MLflow training run to bind back to the exact governed dataset
state, orchestration context, feature definition, code revision, and dataset
contract used during training. MLflow tracking alone does not provide that join;
Dagster asset metadata and dataset lineage evidence do not cover ML runs.

## Decision

Every ML experiment run must carry a validated **five-tuple** before it is
accepted as governed evidence:

| Field | Source |
|---|---|
| `iceberg_snapshot_id` | Current Iceberg snapshot of the training dataset at run start |
| `dagster_run_id` | Active Dagster run materializing `ml_experiment` |
| `feature_version` | Stable identifier for the model feature set (`FEATURE_VERSION`) |
| `code_commit` | `GIT_COMMIT` env var or `git rev-parse HEAD` |
| `data_contract_hash` | SHA-256 of the canonical JSON for the governed dataset contract |

Implementation:

- `governance/ml_lineage.py` defines `MLLineageTuple`, validation, and MLflow tag binding.
- `ml/evaluate.run_experiment_set()` requires a tuple and tags every MLflow run.
- `dagster/assets.py` builds the tuple for `ml_experiment` and records it in asset metadata.
- Docker Compose passes `GIT_COMMIT` into Dagster services; the Makefile exports it from the host checkout.

Training and experiment orchestration **fail fast** when any required field is missing or invalid.

## Consequences

- MLflow runs become resolvable to Iceberg snapshot, Dagster run, code, features, and contract hash.
- `make demo` and CI require a git checkout (or explicit `GIT_COMMIT`) for the ML step.
- Model-card generation (E4) and evaluation evidence can reuse the same tuple and digest.

## Alternatives Considered

- **MLflow tags only, no schema** — rejected; tags drift and are not hash-bound.
- **Dagster metadata only** — rejected; MLflow runs are the audit surface for experiments.
- **Timestamp alignment** — rejected; not deterministic or verifiable.

## Related

- [ADR-011](ADR-011-v3-ml-productization-boundary.md) — serving stays out of scope
- [ADR-021](ADR-021-agent-policy-hooks-metadata-first.md) — policy enforcement boundary for v2.8
