# SoloLakehouse Timeline

This document records version evolution in release order.

## v1.0.0 (2026-03-26) - Delivered (historical)

Theme:
- Runnable baseline lakehouse core.

What landed:
- MinIO, PostgreSQL, Hive Metastore, Trino, MLflow baseline.
- End-to-end medallion data flow and ML experiment logging.

## v2.0.0 (2026-03-28) - Delivered (historical)

Theme:
- Dagster orchestration introduction.

What landed:
- Software-defined assets and `full_pipeline_job`.
- Schedule, sensor, and asset check governance primitives.

## v2.5.0 (2026-03-28) - Delivered

Theme:
- Single-track runtime standardization and platform completeness.

What landed:
- Iceberg Gold path via Trino.
- OpenMetadata integrated in default stack.
- Superset integrated in default stack.
- Legacy parallel runtime paths removed from code.

Decision gate to v3:
- Harden infrastructure/governance without reintroducing parallel runtime entrypoints.

## v2.5.1 (2026-05-10) - Current baseline (frozen)

Theme:
- v2.5 freeze hardening — close the acceptance gate so v2.6 work can begin.

What landed:
- `make demo` acceptance entrypoint (`demo_data_flow_job` + Trino Hive/Iceberg
  Gold row-count assertions).
- Root `DEMO.md` + `RUNBOOK.md` + cold-clone hardware/OS matrix in README.
- GitHub Actions `compose-demo` gate runs `make setup` + `make demo` from a
  clean CI runner.
- `docs/v2.5-acceptance-criteria.md` checklist closed (cold clone, demo
  readiness, documentation completeness, stability boundary).
- ADR-019 records the MinIO → SeaweedFS deferral that locks v2.5 freeze scope.

Decision gate to v2.6 / Phase 1 of entity split:
- Treat v2.5.1 as the frozen template baseline; new work goes to v2.6 or the
  entity-template preparation track.

## Post-v2.5 entity-template preparation - Phase 1 complete (2026-05-18)

Theme:
- Turn the frozen v2.5 reference runtime into a repeatable product-entity
  template, so FinLakehouse and Aviation Lakehouse can be split out without
  changing application code.

Delivered scope (evidence in `docs/entity-template-readiness.md`):
- Product entity contract defines identity, storage, runtime, metadata,
  backup, and side-by-side upgrade fields
  (`docs/product-entity-contract.md`).
- Runtime identity parameterized via `runtime_identity.py` + `.env.example`
  (`PRODUCT_ID`, `PRODUCT_DISPLAY_NAME`, `RUNTIME_VERSION`, `TRINO_USER`, etc.).
- Storage locations parameterized via `storage_config.py`
  (`DATA_BUCKET`, `AUDIT_BUCKET`, `MLFLOW_ARTIFACT_BUCKET`, `WAREHOUSE_URI`).
- MinIO retained as current S3-compatible provider, decoupled from product
  identity (`docs/object-store-abstraction.md` + ADR-019).
- Stable logical dataset IDs (`fin.*`, `aviation.*`) defined and mapped to
  physical assets (`docs/dataset-governance-naming.md`).
- Entity-owned runtime root layout `/opt/<product_id>/{app,data,backup,logs}`
  documented (`docs/runtime-state-layout.md`).
- Backup/restore runbook + one passing disposable restore drill
  (`docs/entity-backup-restore-runbook.md` +
  `docs/restore-drills/2026-05-17-entity-template-restore-drill.md`).
- Lightweight SLH portal as shared operator/demo entrypoint
  (`scripts/health-server.py` + `make health`).

Next decision gate (Phase 2):
- Split out FinLakehouse on a dedicated VPS using the prepared template,
  keeping MinIO; do not combine with object-store replacement or v2.6
  governance evidence work.

## v3.0.0 - Planned

Theme:
- Production infrastructure and governance hardening.

Focus:
- Multi-environment deployment model.
- Promotion controls, rollback strategy, secrets governance.
- SLO-driven observability and incident workflows.

## v4.0.0 - Planned

Theme:
- Self-serve usability and operational clarity.
