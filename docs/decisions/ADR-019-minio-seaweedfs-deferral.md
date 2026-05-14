# ADR-019: Defer MinIO to SeaweedFS Migration

**Status:** Accepted  
**Date:** 2026-05-10

## Context

SoloLakehouse v2.5 uses MinIO as the S3-compatible object store for Bronze, Silver, Gold staging, and MLflow artifacts. SeaweedFS remains an attractive future option because it can model large object workloads with different operational trade-offs and can be useful when the project needs to discuss object-store portability beyond a single-node MinIO baseline.

The v2.5 acceptance goal is different: freeze a trustworthy local baseline that a stranger can start, verify, and demo. Replacing object storage during the freeze phase would increase risk in the most sensitive path of the system: ingestion output, Trino/Hive external table reads, Iceberg Gold creation, and MLflow artifact storage.

## Decision

Keep MinIO as the v2.5 object storage baseline and defer any MinIO to SeaweedFS migration until after the v2.5 freeze.

The migration remains a future portability exercise, not a v2.5 deliverable.

## Consequences

- v2.5 remains stable around a well-known S3-compatible development object store.
- Existing Trino, Hive Metastore, Dagster, and MLflow configuration remains unchanged.
- Demo and CI hardening can focus on repeatability instead of storage migration.
- The project must avoid describing SeaweedFS as part of the active v2.5 runtime.

## Alternatives Considered

### Migrate during v2.5 freeze

- Pros: broader storage-portability story sooner.
- Cons: high regression risk across every data path; distracts from cold-clone and demo readiness.
- Rejected for v2.5.

### Add SeaweedFS as an optional profile

- Pros: enables experiments without removing MinIO.
- Cons: doubles documentation and support burden during the freeze phase.
- Rejected for v2.5; reconsider after the baseline is frozen.

### Keep MinIO permanently

- Pros: simplest operational path.
- Cons: weakens the future portability story.
- Rejected as a permanent decision; accepted only as the v2.5 boundary.

## Follow-up

Revisit object storage portability in a later version after the v2.5 cold-clone,
demo, documentation, and CI gates are green.

During entity-template preparation, use
[Object Store Abstraction and MinIO Deferral](../object-store-abstraction.md) to
separate product-level S3-compatible object-store configuration from
MinIO-specific runtime settings.
