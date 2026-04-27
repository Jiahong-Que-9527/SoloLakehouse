# SoloLakehouse

<p align="center">
  <img src="docs/img/slh-brand.png" width="300" alt="SoloLakehouse">
</p>

<h3 align="center">A local-first lakehouse reference architecture for production-minded data platform engineering.</h3>

<p align="center">
  MinIO · Trino · Iceberg · Dagster · MLflow · OpenMetadata · Superset
</p>

<p align="center">
  <a href="https://github.com/Jiahong-Que-9527/SoloLakehouse/actions/workflows/test.yml"><img src="https://github.com/Jiahong-Que-9527/SoloLakehouse/actions/workflows/test.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.13%2B-blue.svg" alt="Python 3.13+">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/runtime-Docker%20Compose-2496ED.svg" alt="Docker Compose">
  <img src="https://img.shields.io/badge/table%20format-Iceberg-5C7CFA.svg" alt="Apache Iceberg">
</p>

<p align="center">
  <a href="#quick-start"><strong>Run locally</strong></a>
  ·
  <a href="docs/architecture.md"><strong>Architecture</strong></a>
  ·
  <a href="docs/decisions/README.md"><strong>ADRs</strong></a>
  ·
  <a href="docs/ASSESSMENT_LAKEHOUSE_DAX_ECB.md"><strong>Self-assessment</strong></a>
</p>

---

SoloLakehouse is a readable, runnable, cloud-neutral lakehouse reference architecture. It shows how the pieces behind a modern data platform fit together without relying on a managed SaaS layer.

It is not a framework or library. It is a production-minded reference stack you can run locally, inspect end to end, fork, critique, and extend.

<p align="center">
  <img src="docs/img/SLHv2.5-architecture.jpg" alt="SoloLakehouse v2.5 architecture">
</p>

<p align="center">
  <em>v2.5 baseline: local-first lakehouse with orchestration, governance, BI, ML tracking, and Iceberg Gold tables.</em>
</p>

## Why It Exists

SoloLakehouse is built for engineers who want to understand and own the operating model behind platforms like Databricks and Snowflake, not only consume them.

The project focuses on:

- **Cloud independence:** run the lakehouse locally with open-source components.
- **Compliance awareness:** make data boundaries, metadata, release checks, and architecture decisions visible.
- **Portability:** keep storage, orchestration, catalog, BI, and deployment layers replaceable.
- **Senior platform signal:** demonstrate system design, governance thinking, CI, ADRs, roadmap ownership, and operational trade-offs.

Useful for data platform engineers, analytics/ML engineers, enterprise architects, and recruiters evaluating senior engineering credibility.

## Quick Start

Requirements: Docker with the Compose plugin, Python 3.13+, and `make`.

```bash
git clone https://github.com/Jiahong-Que-9527/SoloLakehouse.git
cd SoloLakehouse
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make setup
```

Validate the stack and run the pipeline:

```bash
make verify
make pipeline
```

Key UIs:

- Dagster: `http://localhost:3000`
- Superset: `http://localhost:8088`
- OpenMetadata: `http://localhost:8585`
- MLflow: `http://localhost:5000`
- Trino: `http://localhost:8080`
- MinIO Console: `http://localhost:9001`

See [docs/quickstart.md](docs/quickstart.md) and [docs/deployment.md](docs/deployment.md) for details, sizing, credentials, and troubleshooting.

## What It Demonstrates

- End-to-end medallion flow: **sources -> Bronze -> Silver -> Gold -> BI / ML**.
- Dagster asset orchestration with jobs, schedules, sensors, and checks.
- Trino SQL over Hive and Iceberg catalogs.
- Gold-layer Iceberg tables managed through Trino.
- MLflow experiment tracking with artifacts on object storage.
- OpenMetadata catalog integration and Superset BI access.
- CI, release checks, ADRs, and a candid self-assessment of current limits.

Current demo data uses ECB SDW API data and DAX sample data. The active runtime is **v2.5 only**; historical v1/v2 material lives in [docs/history/](docs/history/).

## Architecture

```text
Data sources
  -> Python ingestion + validation
  -> MinIO Bronze/Silver Parquet
  -> Trino + Hive Metastore
  -> Iceberg Gold tables
  -> Superset dashboards + MLflow experiments

Platform services:
  PostgreSQL, Dagster, OpenMetadata, Superset, MLflow
```

The detailed architecture is in [docs/architecture.md](docs/architecture.md), and the medallion conventions are in [docs/medallion-model.md](docs/medallion-model.md).

## Evolution Roadmap

- **v1.0:** local medallion lakehouse foundation.
- **v2.0:** Dagster orchestration introduced.
- **v2.5:** current single runtime with Iceberg Gold, OpenMetadata, Superset, and Dagster-first execution.
- **v3.0 planned:** Kubernetes, Helm, Terraform, secrets governance, access controls, SLOs, and promotion/rollback patterns.
- **v4.0 planned:** self-serve usability and stronger operational polish.

See [docs/roadmap.md](docs/roadmap.md) for the canonical roadmap.

## Portability Notes

The stack is intentionally built around replaceable boundaries:

- MinIO can evolve toward SeaweedFS, Ceph, or cloud object storage.
- Docker Compose can evolve toward Kubernetes, Helm, and Terraform.
- Local PostgreSQL can evolve toward managed or HA PostgreSQL.
- Superset and OpenMetadata can be swapped for enterprise BI/catalog tools.
- Local secrets can evolve toward Vault or cloud secret managers.

These trade-offs are documented in the [ADR index](docs/decisions/README.md).

## Demo Visuals

Screenshot placeholders are reserved for the next visual pass:

- `docs/img/readme/dagster.png`
- `docs/img/readme/superset.png`
- `docs/img/readme/openmetadata.png`
- `docs/img/readme/mlflow.png`
- `docs/img/readme/trino.png`
- `docs/img/readme/minio.png`

## Documentation

- [Architecture](docs/architecture.md)
- [Quick start](docs/quickstart.md)
- [Deployment](docs/deployment.md)
- [Roadmap](docs/roadmap.md)
- [ADR index](docs/decisions/README.md)
- [Demo runbook](docs/DEMO_RUNBOOK_EN.md)
- [User guide](docs/USER_GUIDE_EN.md)
- [Self-assessment](docs/ASSESSMENT_LAKEHOUSE_DAX_ECB.md)

## Feedback

If this architecture is useful, star the repo so more platform engineers can find it.

Architecture critiques are welcome, especially around governance hardening, migration paths, and v3 productionization priorities.

## License

[MIT](LICENSE)
