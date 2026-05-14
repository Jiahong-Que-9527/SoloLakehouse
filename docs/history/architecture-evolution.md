# Architecture Evolution and Planning Choices

This file explains major architecture choices over time and why they changed.

## v1 Foundation Choices (implemented)

1) Docker Compose first, Kubernetes later  
- Selected: Docker Compose  
- Why: low setup friction and faster local iteration.

2) Trino + Hive Metastore query model  
- Selected: Trino over embedded query-only engines  
- Why: better demonstration of metadata-driven lakehouse patterns.

3) Parquet-first medallion flow  
- Selected: Parquet append-only conventions for Bronze/Silver/Gold  
- Why: lower operational complexity for a reference implementation.

## v2 Orchestration Choices (implemented, historical)

1) Orchestrator selection  
- Candidates: Dagster, Prefect, Airflow, script+cron  
- Selected: Dagster.

2) Runtime convergence decision  
- Historical state: v2 initially kept dual runtime paths for migration.  
- Current state: dual paths retired; orchestration is Dagster-only in active runtime.

## v2.5 Baseline Choices (implemented, current)

1) Iceberg for Gold  
- Selected: Trino-managed Iceberg Gold table while preserving Python Parquet staging.

2) Metadata and BI stack posture  
- Selected: OpenMetadata + Superset as required platform components in default runtime.

3) Single runtime entrypoint  
- Selected: `make pipeline` (Dagster `full_pipeline_job`) as only execution path.

## Post-v2.5 Entity Template Choices (in progress)

1) Product entity contract before product split
- Selected: define a required entity contract before launching FinLakehouse or
  Aviation Lakehouse as long-running runtimes.
- Why: stable product identity, dataset namespace, storage locations, metadata
  labels, runtime roots, and upgrade policy need to be explicit before data
  assets become long-lived.
- Alternative rejected: copy the v2.5 runtime first and rename values later.
  That would mix product identity changes with storage/runtime migration risk.

2) MinIO retained for the first split
- Selected: keep MinIO as the initial S3-compatible provider while naming the
  object-store boundary generically in product-level configuration.
- Why: entity split, object-store replacement, and v2.6 governance evidence are
  separate risk surfaces and should be validated independently.

3) Logical dataset IDs as governance join keys
- Selected: use stable `fin.*` and `aviation.*` dataset IDs that map to current
  object-store paths, Trino tables, OpenMetadata entities, and Dagster assets.
- Why: v2.6 lineage evidence and future storage migrations need a stable key
  that is not tied to MinIO bucket names, warehouse URIs, or catalog table
  names.
- Alternative rejected: use physical paths or Trino table names as governance
  identities. Those names are expected to change during entity split and
  side-by-side migration.

## v3 Decision Frame (planned)

- Multi-environment deployment architecture
- Promotion and rollback governance
- Secrets/access model and auditability
- SLO/alerting and incident readiness

## Legacy Record

Historical migration and compatibility details remain documented for reference only:
- `docs/history/legacy-overview.md`
