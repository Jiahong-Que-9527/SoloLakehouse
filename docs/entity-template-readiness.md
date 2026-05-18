# Entity Template Readiness Evidence

This document closes the Phase 1 readiness loop for using SoloLakehouse v2.5
as a repeatable product-entity template before creating FinLakehouse and
Aviation Lakehouse instances.

Phase 1 prepares one configurable baseline. It does not create the long-running
product entities; that remains Phase 2 work.

## Readiness Decision

SoloLakehouse v2.5 is ready to be used as the entity template for the first
split when the target entity keeps MinIO as the initial S3-compatible object
store and follows the documented backup, restore, and side-by-side migration
contracts.

OpenMetadata catalog-history continuity is not required for Phase 1. The
accepted strategy is service restoration plus catalog re-ingestion unless a
future entity explicitly validates a history-preserving dump/import path.

## Exit Criteria Evidence

| Exit criterion | Status | Evidence |
|---|---|---|
| Entity contract exists | Complete | [product-entity-contract.md](product-entity-contract.md) defines identity, storage, runtime, metadata, backup, and side-by-side upgrade fields. |
| Runtime identity is configurable | Complete | [product-entity-contract.md](product-entity-contract.md), [runtime-state-layout.md](runtime-state-layout.md), and `.env.example` define `PRODUCT_ID`, `ENVIRONMENT`, `RUNTIME_VERSION`, URLs, and entity-local roots. |
| Data, audit, MLflow, and warehouse locations are configurable | Complete | [object-store-abstraction.md](object-store-abstraction.md) and [product-entity-contract.md](product-entity-contract.md) define `DATA_BUCKET`, `AUDIT_BUCKET`, `MLFLOW_ARTIFACT_BUCKET`, and `WAREHOUSE_URI`. |
| Lightweight portal exists as the shared operator/demo entrypoint | Complete | `portal/` and [README.md](../README.md) expose entity identity, health, demo readiness, and links to the core UIs. |
| Runtime state ownership is documented for product entities | Complete | [runtime-state-layout.md](runtime-state-layout.md) defines `/opt/<product_id>/app`, `data`, `backup`, `logs`, and `.env` ownership. |
| Backup and restore procedure is documented and tested once | Complete | [entity-backup-restore-runbook.md](entity-backup-restore-runbook.md) defines the procedure; [restore-drills/2026-05-17-entity-template-restore-drill.md](restore-drills/2026-05-17-entity-template-restore-drill.md) records the passing disposable restore drill. |
| Dataset ID naming convention exists | Complete | [dataset-governance-naming.md](dataset-governance-naming.md) defines stable logical IDs and physical mapping rules. |
| MinIO is treated as the current S3-compatible provider, not product identity | Complete | [object-store-abstraction.md](object-store-abstraction.md) and [decisions/ADR-019-minio-seaweedfs-deferral.md](decisions/ADR-019-minio-seaweedfs-deferral.md) define the provider boundary and defer replacement. |

## Phase 2 Handoff

Before creating long-running product entities:

1. Create a product-specific `.env` from the entity contract.
2. Use an entity-owned runtime root such as `/opt/<product_id>/`.
3. Keep MinIO for the first split unless a separate object-store migration plan
   is approved.
4. Run `make verify`, `make demo`, and the backup/restore drill for the target
   entity before cutover.
5. Record any entity-specific OpenMetadata re-ingestion steps as restore
   evidence.
