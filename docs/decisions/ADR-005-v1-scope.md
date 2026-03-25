# ADR-005: Why v1 Excludes Prometheus, Grafana, and CloudBeaver

**Status:** Accepted
**Date:** 2024-01

## Context

The original SoloLakehouse plan included 8 Docker services: the 5 core services (MinIO, PostgreSQL, Hive Metastore, Trino, MLflow) plus CloudBeaver, Prometheus, and Grafana. During architecture review, the 3 additional services were removed from v1.

## Decision

Prometheus, Grafana, and CloudBeaver are moved to v2. v1 ships with 5 services only.

## Rationale

**1. CloudBeaver provides no capability that Trino CLI or DBeaver Desktop cannot.**
CloudBeaver is a web-based SQL IDE that connects to Trino. Its value is "SQL in the browser without installing anything". But any evaluator of this project already has DBeaver, TablePlus, DataGrip, or similar desktop clients. Adding a 6th Docker service for a web SQL UI — when the Trino web UI at `:8080` already shows query status — is pure overhead with no substantive demonstration value.

**2. Prometheus + Grafana in v1 would be cosmetic, not functional.**
Prometheus and Grafana are genuinely powerful observability tools. But their value depends entirely on what metrics you expose. In v1:
- Docker container metrics (CPU, memory) are the default — a 3-line scrape config. This is trivially shallow.
- Application-level metrics (ingestion latency, data quality scores, ML training duration) require custom instrumentation that is itself a non-trivial engineering effort.

A hiring manager who opens Grafana and sees only default Docker container dashboards may conclude the candidate does not understand what meaningful observability looks like. This is worse than having no Grafana at all.

**3. 5 services vs 8 services: startup time, resource usage, and debugging complexity.**
Removing 3 services:
- Reduces `make up` startup time by ~30 seconds
- Reduces RAM requirements by ~500 MB (CloudBeaver ~300 MB, Prometheus ~100 MB, Grafana ~100 MB)
- Reduces the number of potential failure points from 8 to 5
- Simplifies the dependency graph

For a demo platform intended to be spun up and down frequently, this matters.

**4. Scope control is itself a senior engineering skill.**
The decision to cut these 3 services and document why is more impressive to a hiring manager than having all 8 services running with shallow configurations. Knowing what NOT to build — and being able to articulate the reasoning — is a hallmark of senior engineering judgment.

## Upgrade Path

**v2** will include Prometheus and Grafana with meaningful, custom pipeline metrics:
- `pipeline_ingestion_duration_seconds` — time to complete Bronze ingestion
- `pipeline_data_quality_score` — ratio of valid vs rejected records
- `pipeline_silver_row_count` — rows written to Silver layer
- `mlflow_training_duration_seconds` — time to complete a training run

These metrics transform Grafana from "decorative" to "genuinely useful for operational visibility".

CloudBeaver may be included in v2 as a convenience feature for non-technical evaluators who do not have a SQL client installed.
