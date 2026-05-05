# ADR-018: ML Lineage Five-Tuple

**Status:** Placeholder
**Target version:** v2.8
**Related work:** E18, Block E

## Context

v2.8 needs every MLflow run to be traceable back to the exact data, orchestration context, code, and governance contract used during training. The current MLflow tracking is useful, but the binding to Iceberg and Dagster evidence is not yet formalized.

## Decision To Make

Confirm the required five-tuple for every training run:

- `iceberg.snapshot_id`
- `dagster.run_id`
- `feature_version`
- `code_commit`
- `data_contract_hash`

Training should fail fast when any required field is missing.

## Evidence Required

- A given MLflow run id can resolve to an Iceberg snapshot, Dagster run, code commit, feature version, and data contract hash.
- Model-card generation consumes the same five-tuple.
- Missing or inconsistent fields fail before a run is accepted as release evidence.

## Alternatives To Compare

- Rely on timestamps and MLflow tags only.
- Store lineage only in Dagster asset metadata.
- Store lineage only in generated model cards.

## Follow-Up

Replace this placeholder with a full ADR when v2.8 E18 implementation starts.
