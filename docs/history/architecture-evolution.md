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

## v3 Decision Frame (planned)

- Multi-environment deployment architecture
- Promotion and rollback governance
- Secrets/access model and auditability
- SLO/alerting and incident readiness

## Legacy Record

Historical migration and compatibility details remain documented for reference only:
- `docs/history/legacy-overview.md`
