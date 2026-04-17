# SoloLakehouse — Architecture

## Overview

SoloLakehouse is a **Lakehouse reference implementation** standardized on a **single v2.5 runtime path**.
The local/reference deployment runs on one Docker Compose host with **MinIO**, **PostgreSQL**, **Hive Metastore**, **Trino**, **MLflow**, **Dagster**, **OpenMetadata**, and **Superset**.

The active architecture centers on five data/runtime layers (sources -> ingestion -> medallion storage -> query -> ML) plus platform services for orchestration, metadata, and BI access.
Earlier version milestones and migration narratives are preserved in **[history/README.md](history/README.md)**.

## Diagram — v2.5 baseline

![SoloLakehouse v2.5 architecture](img/SLHv2.5-architecture.jpg)

*Image source: `docs/img/SLHv2.5-architecture.jpg` (JPG).*

## Layers (core)

```
Layer 1 — Data Sources: ECB SDW REST API + DAX daily CSV (sample)
    │
    ▼
Layer 2 — Ingestion & Validation: Python collectors + Pydantic + structlog
    │
    ▼
Layer 3 — Lakehouse storage (Medallion): MinIO; Bronze/Silver as Parquet files; **Gold** registered as **Apache Iceberg** in Trino (`iceberg` catalog) after Parquet staging (see [ADR-013](decisions/ADR-013-iceberg-gold-trino.md))
    │
    ▼
Layer 4 — Compute & Query: Trino ↔ Hive Metastore ↔ PostgreSQL
    │
    ▼
Layer 5 — ML: MLflow (tracking + artifacts on MinIO + PostgreSQL)
```

## Orchestration Layer (v2)

v2 introduces Dagster as the default orchestrator for asset-aware execution, retries, scheduling, and lineage.

### Dagster assets

- `ecb_bronze`
- `dax_bronze`
- `ecb_silver`
- `dax_silver`
- `gold_features`
- `ml_experiment`

### Asset dependency graph (ASCII)

```text
ecb_bronze      dax_bronze
    |               |
ecb_silver      dax_silver
      \           /
       \         /
        gold_features
              |
         ml_experiment
```

### Scheduling and automation

- Job: `full_pipeline_job`
- Schedule: `daily_pipeline_schedule`
- Cron: `0 6 * * 1-5` (06:00 UTC, weekdays)
- Sensor: `ecb_data_freshness_sensor` checks ECB freshness every 30 minutes and can trigger `ecb_bronze` when stale.

### Runtime model

- `dagster-webserver` provides UI and job execution entrypoint on port `3000`.
- `dagster-daemon` evaluates schedules/sensors and launches runs.
- Dagster instance storage uses PostgreSQL database `dagster_storage` for persisted run and event history.

## Components (current local/reference stack)

| Component | Role | Port |
|-----------|------|------|
| **MinIO** | S3-compatible storage for Parquet and MLflow artifacts | 9000 (API), 9001 (Console) |
| **PostgreSQL** | Backend for Hive Metastore and MLflow | 5432 |
| **Hive Metastore** | Table metadata (schema, partitions, locations) | 9083 |
| **Trino** | SQL over the lakehouse (Hive + Iceberg catalogs, shared Hive Metastore) | 8080 |
| **OpenMetadata** | Data catalog UI; Trino metadata ingestion | 8585 |
| **Elasticsearch** | Search backend for OpenMetadata | 9200 |
| **OpenMetadata MySQL** | Application database for OpenMetadata | 3307 (host) |
| **Apache Superset** | BI / SQL UI over Trino; dashboards and chart exploration | 8088 |
| **MLflow** | Experiments and model artifacts | 5000 |
| **Dagster Webserver** | Orchestration UI + run entrypoint | 3000 |
| **Dagster Daemon** | Schedules/sensors evaluator and run launcher | N/A (internal) |

## Service dependencies

```
postgres ──► hive-metastore ──► trino
postgres ──► mlflow
postgres ──► dagster-webserver
postgres ──► dagster-daemon
postgres ──► superset
om-mysql  ──► openmetadata-server
om-elasticsearch ──► openmetadata-server
minio    ──► trino
minio    ──► mlflow
minio    ──► ingestion (Bronze writes)
minio    ──► dagster assets runtime
hive-metastore ──► trino
trino    ──► superset
trino    ──► openmetadata-server
dagster-daemon ──► dagster-webserver (automation and run control)
```

## Medallion (summary)

- **Bronze:** Raw, immutable, partitioned by `ingestion_date`; metadata columns `_ingestion_timestamp`, `_source`.
- **Silver:** Cleaned types, deduplicated, derived fields (e.g. `rate_change_bps`, `daily_return`).
- **Gold:** ML-ready features (e.g. one row per ECB event for the demo model).

Details: **[medallion-model.md](medallion-model.md)**.

## Historical evolution

Current runtime guidance is intentionally limited to the v2.5 baseline.
Earlier v1/v2 build-out stages and migration decisions remain available as narrative context under:

- [history/timeline.md](history/timeline.md)
- [history/architecture-evolution.md](history/architecture-evolution.md)
- [history/legacy-overview.md](history/legacy-overview.md)

## Design decisions (ADRs)

| ADR | Topic |
|-----|--------|
| [ADR-001](decisions/ADR-001-docker-compose.md) | Docker Compose vs Kubernetes |
| [ADR-002](decisions/ADR-002-trino-vs-duckdb.md) | Trino vs DuckDB |
| [ADR-003](decisions/ADR-003-parquet-vs-delta.md) | Parquet vs Delta Lake |
| [ADR-004](decisions/ADR-004-financial-dataset.md) | ECB + DAX data |
| [ADR-005](decisions/ADR-005-v1-scope.md) | Why Prometheus / Grafana / CloudBeaver ship after the five-service core (ADR-005) |
| [ADR-006](decisions/ADR-006-v2-dagster-orchestration.md) | v2 Dagster orchestration migration and transition fallback (historical) |
| [ADR-007](decisions/ADR-007-v3-k8s-helm-terraform.md) | v3 Kubernetes + Helm + Terraform baseline |
| [ADR-008](decisions/ADR-008-v3-environment-promotion.md) | v3 environment promotion gates |
| [ADR-009](decisions/ADR-009-v3-secrets-and-access-governance.md) | v3 secrets and access governance |
| [ADR-010](decisions/ADR-010-v3-observability-and-slo.md) | v3 SLO-driven observability |
| [ADR-011](decisions/ADR-011-v3-ml-productization-boundary.md) | v3 ML productization boundary |
| [ADR-012](decisions/ADR-012-v3-data-governance-catalog-strategy.md) | v3 data governance catalog strategy |
| [ADR-013](decisions/ADR-013-iceberg-gold-trino.md) | Iceberg for Gold via Trino |
| [ADR-014](decisions/ADR-014-openmetadata-optional-profile.md) | OpenMetadata optional compose profile at introduction time (historical) |
