# SoloLakehouse — Architecture

## Overview

SoloLakehouse is a **Lakehouse reference implementation** on a single Docker Compose host: **MinIO**, **PostgreSQL**, **Hive Metastore**, **Trino**, **MLflow**, with schema validation, structured logging, and **immutable** Bronze storage.

The **five-layer core** (sources → ingestion → medallion storage → query → ML) is the **foundation** for **v1.0**, which targets a full **eight-layer** stack (metadata, observability, user access). See **[roadmap.md](roadmap.md)**.

## Diagram — five-layer core

![Five-layer core architecture](img/SLH_arch_v0.1.svg)

*Vector source: `docs/img/SLH_arch_v0.1.svg`. You can replace with a PNG of the same basename if preferred.*

## Layers (core)

```
Layer 1 — Data Sources: ECB SDW REST API + DAX daily CSV (sample)
    │
    ▼
Layer 2 — Ingestion & Validation: Python collectors + Pydantic + structlog
    │
    ▼
Layer 3 — Lakehouse storage (Medallion): MinIO, Parquet — bronze / silver / gold
    │
    ▼
Layer 4 — Compute & Query: Trino ↔ Hive Metastore ↔ PostgreSQL
    │
    ▼
Layer 5 — ML: MLflow (tracking + artifacts on MinIO + PostgreSQL)
```

## Components

| Component | Role | Port |
|-----------|------|------|
| **MinIO** | S3-compatible storage for Parquet and MLflow artifacts | 9000 (API), 9001 (Console) |
| **PostgreSQL** | Backend for Hive Metastore and MLflow | 5432 |
| **Hive Metastore** | Table metadata (schema, partitions, locations) | 9083 |
| **Trino** | SQL over the lakehouse via Hive connector | 8080 |
| **MLflow** | Experiments and model artifacts | 5000 |

## Service dependencies

```
postgres ──► hive-metastore ──► trino
postgres ──► mlflow
minio    ──► trino
minio    ──► mlflow
minio    ──► ingestion (Bronze writes)
```

## Medallion (summary)

- **Bronze:** Raw, immutable, partitioned by `ingestion_date`; metadata columns `_ingestion_timestamp`, `_source`.
- **Silver:** Cleaned types, deduplicated, derived fields (e.g. `rate_change_bps`, `daily_return`).
- **Gold:** ML-ready features (e.g. one row per ECB event for the demo model).

Details: **[medallion-model.md](medallion-model.md)**.

## Target state — v1.0

![SoloLakehouse v1.0 Enterprise Architecture](img/SLH_arch_v1.0.svg)

Eight-layer enterprise layout: multi-source ingestion, dedicated metadata layer, observability (Prometheus + Grafana), user access (e.g. CloudBeaver). Scope and phasing: [roadmap.md](roadmap.md).

## Design decisions (ADRs)

| ADR | Topic |
|-----|--------|
| [ADR-001](decisions/ADR-001-docker-compose.md) | Docker Compose vs Kubernetes |
| [ADR-002](decisions/ADR-002-trino-vs-duckdb.md) | Trino vs DuckDB |
| [ADR-003](decisions/ADR-003-parquet-vs-delta.md) | Parquet vs Delta Lake |
| [ADR-004](decisions/ADR-004-financial-dataset.md) | ECB + DAX data |
| [ADR-005](decisions/ADR-005-v1-scope.md) | Why Prometheus / Grafana / CloudBeaver ship after the five-service core (ADR-005) |
