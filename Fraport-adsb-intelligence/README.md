# Fraport ADS-B Intelligence

Build an aviation data foundation for Frankfurt Airport (ICAO `EDDF`) from
OpenSky Network state vectors. The programme starts with a reliable historical
acquisition tool and grows through transformation, a governed data release, a
cloud Gold layer, analytics, a taxi-in time model, serving and orchestration.

The raw research data stays on the local machine. Bronze and Silver are built
locally, and only the Gold data product crosses to Google Cloud, as a versioned
release. Each subproject chooses the runtime that fits its workload.

**Status (2026-11-15):** acquisition gate G0 has passed. Batches b01 (2026-10)
through b04 (2026-04) are validated, accepted and backed up to `E:`. The next
work is batch b05 (2026-09). Details are in the
[acquisition status](01-opensky-acquisition/README.md#status-2026-11-15).

## Subprojects

| # | Subproject | Runtime | Focus |
|---|------------|---------|-------|
| 01 | [OpenSky Acquisition](01-opensky-acquisition/README.md) | Local | Ingestion, reliability, data manifest |
| 02 | [Aviation Transformation](02-aviation-transformation/README.md) | Local (Python, DuckDB) | Silver, Gold, Release Gate |
| 03 | [Airport Analytics](03-airport-analytics/README.md) | GCP (Terraform, GCS, BigQuery) | Cloud Gold, SQL, infrastructure as code |
| 04 | [Aviation Lakehouse Integration](04-aviation-lakehouse/README.md) | Databricks, reads Gold releases | Spark, Delta Lake, governance |
| 05 | [Taxi-in Prediction](05-taxi-in-prediction/README.md) | Vertex AI | Features, training, evaluation |
| 06 | [Model Serving Integration](06-model-serving/README.md) | Cloud Run | API, versioning, monitoring |
| 07 | [Platform Orchestration](07-platform-orchestration/README.md) | GCP Workflows or Dagster | Scheduling, lineage, recovery |

Subprojects 04 and 06 are the aviation workloads on the
[Databricks](../databricks/README.md) and [Google Cloud](../gcp/README.md)
roadmaps. They reuse those platforms' delivery and governance practices. They
do not duplicate a separate lakehouse or serving project.

## Documents

- [Project plan](docs/project-plan.md) covers phases, milestones, dependencies
  and exit criteria.
- [ADR-001](docs/adr/ADR-001-local-execution-for-historical-acquisition.md)
  records why historical acquisition runs locally.
- [ADR-002](docs/adr/ADR-002-regional-dataset-and-monthly-batches.md) records
  the 75 km regional dataset and the monthly batch approach.
- [ADR-003](docs/adr/ADR-003-local-bronze-silver-published-gold.md) records
  why Bronze and Silver stay local and only Gold is published.
- [ADR-004](docs/adr/ADR-004-gold-table-format-and-catalog.md) records the
  Gold table format decision and the check that must pass first.
- [01 design](01-opensky-acquisition/docs/design.md) and
  [batch plan](01-opensky-acquisition/docs/batch-plan.md) describe how the
  first dataset is collected. Original consulting notes and exploration
  notebooks stay local.

## Principles

- **Workload placement.** Run each workload where it is cheapest and simplest
  to operate. Move it only when a real requirement changes.
- **Code, data and backups are separate.** Git holds code, schemas,
  configuration and documentation. Raw data never goes into this repository.
- **Local source of record, published products.** Bronze and Silver stay on
  the local machine. Gold crosses to the cloud only through a Release Gate:
  versioned, checked, with a manifest and a release ID.
- **Idempotent and traceable.** Repeating a run or ingesting a release again
  never duplicates data. Every output traces to a release ID, a data version
  and a commit.
- **Bronze stays raw.** Acquisition keeps source fields, types and units.
  Cleaning, filtering and inference belong to later subprojects.
- **Proxy labels are not ground truth.** Taxi-in values derived from ADS-B
  state vectors are proxies. Claims about airport ground truth need
  independent validation.
- **Public work.** Raw data stays out of Git and public storage. Public work
  uses code, architecture and synthetic data.
