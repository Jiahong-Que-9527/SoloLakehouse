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

## v2.5.0 (2026-03-28) - Current baseline

Theme:
- Single-track runtime standardization and platform completeness.

What landed:
- Iceberg Gold path via Trino.
- OpenMetadata integrated in default stack.
- Superset integrated in default stack.
- Legacy parallel runtime paths removed from code.

Decision gate to v3:
- Harden infrastructure/governance without reintroducing parallel runtime entrypoints.

## Post-v2.5 entity-template preparation - In progress

Theme:
- Prepare the v2.5 reference runtime to become a repeatable product entity
  template before splitting FinLakehouse and Aviation Lakehouse.

Current scope:
- Define the product entity contract for stable identity, physical runtime
  details, storage locations, service labels, and side-by-side upgrade policy.
- Define stable logical dataset IDs and physical mapping rules for FinLakehouse
  and future Aviation Lakehouse governance evidence.
- Keep MinIO as the initial S3-compatible object-store provider and document
  the product-level object-store configuration boundary for later replacement.

Next decision gate:
- Parameterize runtime identity, data buckets, warehouse URI, MLflow artifacts,
  audit bucket, and entity-local runtime state from the contract.

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
