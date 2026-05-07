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
  <a href="docs/project-state-overview-2026-05-05.md"><strong>Self-assessment</strong></a>
</p>

---

SoloLakehouse is a self-contained, cloud-neutral lakehouse reference platform that shows how the pieces behind a modern, audit-ready data platform fit together without depending on a managed SaaS lakehouse service.

It is built end-to-end on Docker Compose — small enough to read in a weekend, complete enough to discuss production trade-offs, and explicit enough to map onto DORA, BaFin BAIT/MaRisk, and EU AI Act Title III obligations.

## Architecture

<p align="center">
  <img src="docs/img/SLHv2.5_architecutre.png" alt="SoloLakehouse v2.5 architecture">
</p>

<p align="center">
  <em>v2.5 baseline: local-first lakehouse with orchestration, governance, BI, ML tracking, and Iceberg Gold tables.</em>
</p>


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

## What It Solves

Most lakehouse tutorials show **how to plug components together**. SoloLakehouse is built to answer the harder questions a regulated European platform team actually faces:

| Problem the platform answers | How SoloLakehouse addresses it |
|---|---|
| **"If BaFin asks for end-to-end lineage of this Gold table tomorrow, can we deliver it in 24h?"** | Three-source lineage join (OpenMetadata + Iceberg snapshots + Dagster runs) producing signable evidence packs to a WORM bucket. *([v2.6 — planned](docs/history/v2.6-planning.md))* |
| **"Are we locked into our vendor's table format?"** | Iceberg Gold tables readable by Trino today, with documented multi-engine paths (Spark / DuckDB / Flink) and Hive-Metastore ↔ REST-Catalog switch. *([v2.7 — planned](docs/history/v2.7-planning.md))* |
| **"Can we trace any model artifact back to the exact training data, code commit, and orchestration run?"** | MLflow runs bound to Iceberg snapshot id + Dagster run id + code commit + data-contract hash, with auto-generated EU AI Act Art.13 model cards. *([v2.8 — planned](docs/history/v2.8-planning.md))* |
| **"Can the same stack run on a laptop and on Kubernetes without rewriting?"** | All services are containerized, configuration-externalized, state-externalized; v3.0 promotes the same images to K8s + Helm + Terraform. *([v2.9](docs/history/v2.9-planning.md) → [v3.0](docs/history/v3-planning.md))* |


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

## Capabilities Demonstrated (v2.5)

- **Medallion architecture** with strict Bronze immutability, Pydantic-v2 schema validation at ingestion, and Iceberg-backed Gold
- **Asset-aware orchestration** in Dagster — jobs, schedules, sensors, asset checks, and lineage in the UI (not task-based DAGs)
- **Federated query** across Hive (Bronze/Silver) and Iceberg (Gold) catalogs via a single Trino endpoint
- **Open table format discipline** — Iceberg Gold tables managed via Trino CTAS, no proprietary engine lock-in
- **ML governance baseline** — MLflow experiments with object-storage artifacts; `TimeSeriesSplit` CV as a discipline (look-ahead bias is treated as a defect, not a default)
- **Catalog & BI integration** — OpenMetadata for lineage and ownership, Superset for SQL-first BI on Trino
- **Production-minded engineering** — CI gates, type checking, ADRs per non-trivial decision, release notes and planning notes per minor version

The reference data domain is European financial markets — ECB Statistical Data Warehouse interest rates and the DAX equity index — chosen deliberately because it surfaces real-world challenges in temporal joins, look-ahead bias, and regulatory data lineage. The active runtime is **v2.5**; historical v1/v2 material is preserved under [docs/history/](docs/history/).

## Engineering Practices

Beyond the platform features, this is built with explicit engineering discipline a hiring panel can audit:

- **Test discipline** — pure-function transforms unit-tested without Docker; Pydantic v2 schema validation on every Bronze record; quality checks fail-fast rather than silent-degrade
- **Type discipline** — `mypy` over `ingestion/`, `transformations/`, `ml/`, `scripts/`, `dagster/`
- **Lint discipline** — `ruff` enforced in CI
- **Architecture discipline** — every non-trivial decision recorded as an [ADR](docs/decisions/README.md)
- **Release discipline** — version-tagged release notes, planning note per minor version, evolution timeline at [docs/history/timeline.md](docs/history/timeline.md)
- **Observability discipline** — `structlog` JSON events at every step boundary; SLO emit pipeline planned for [v2.9](docs/history/v2.9-planning.md)
- **CI** — GitHub Actions runs lint + typecheck + tests on every push

## Evolution Roadmap

The platform evolves along a single narrative: **first make it run, then make every claim provable on the same Compose stack, and only then migrate the runtime to Kubernetes.** v2.5 is the live runtime today (capabilities listed above). Each minor version after that adds **one category of evidence** the platform can produce — without changing the runtime.

| Version | Theme | Problem | Focus |
|---------|-------|---------|-------|
| **v2.5** *(delivered)* | Platform can run | local-first lakehouse baseline | reproducible Docker Compose stack, Bronze/Silver/Gold flow, Trino, Dagster, MLflow, OpenMetadata, Superset |
| **v2.6** *(planned)* | Platform can produce evidence | regulatory lineage & audit readiness | Dagster + OpenMetadata + Iceberg three-source lineage join, signable audit evidence pack on WORM storage, **DORA 24h / BaFin-style** traceability, data contracts as the gate |
| **v2.7** *(planned)* | Platform can prove openness | data sovereignty & vendor lock-in | multi-engine Iceberg demo (Trino / Spark / DuckDB / Flink), Hive Metastore ↔ Iceberg REST Catalog switch, signable sovereignty report + exit playbook, Databricks-to-Iceberg migration PoC |
| **v2.8** *(planned)* | Platform can govern AI | compliant AI / model traceability | MLflow ↔ Iceberg snapshot five-tuple binding (snapshot_id, dagster.run_id, feature_version, code_commit, data_contract_hash), auto **EU AI Act Art.13** model card, ML asset checks for performance regression *(model serving stays out — ADR-011)* |
| **v2.9** *(planned)* | Platform has production shape | operational readiness | SLO emit + Superset "Platform Health" dashboard, `.env.shared` vs `.env.secrets` discipline, promotion/rollback drill with `make` entrypoints, Iceberg snapshot rollback drill, K8s readiness gate before v3.0 |
| **v3.0** *(planned)* | Platform can run in production | scalable deployment & environment management | Kubernetes, Helm, Terraform, dev/stage/prod separation, managed secrets, GitOps-ready deployment model |
| **v4.0** *(planned)* | Self-serve usability | docs-first onboarding | repeatable verification, clearer failure modes, operational polish |

Per-version planning notes:

- v2.5 — [docs/history/v2.5-planning.md](docs/history/v2.5-planning.md)
- v2.6 — [docs/history/v2.6-planning.md](docs/history/v2.6-planning.md)
- v2.7 — [docs/history/v2.7-planning.md](docs/history/v2.7-planning.md)
- v2.8 — [docs/history/v2.8-planning.md](docs/history/v2.8-planning.md)
- v2.9 — [docs/history/v2.9-planning.md](docs/history/v2.9-planning.md)
- v3.0 — [docs/history/v3-planning.md](docs/history/v3-planning.md)

See [docs/roadmap.md](docs/roadmap.md) for the canonical version status table, and [docs/history/timeline.md](docs/history/timeline.md) for the full evolution timeline.

## Portability & Migration Paths

The platform is built around **replaceable boundaries** — not because every component will be replaced, but because every component **could** be without rewriting the platform contract:

| Boundary | Current (v2.5) | Migration target | Trigger criteria |
|----------|----------------|------------------|------------------|
| Object storage | MinIO | SeaweedFS / Ceph / S3 / GCS | scale beyond single-node throughput; multi-region requirement |
| Runtime | Docker Compose | Kubernetes + Helm + Terraform | multi-environment promotion; HA / SLO requirement *(v3.0)* |
| Metadata DB | Local PostgreSQL 17 | Managed / HA PostgreSQL | RPO < 24h or production SLO commitment |
| Catalog | Hive Metastore | Iceberg REST Catalog | multi-engine demand or vendor-neutral catalog requirement *(v2.7)* |
| Secrets | `.env` files | Vault / cloud KMS | multi-tenant or multi-environment deployment *(v3.0)* |
| BI / Catalog | Superset / OpenMetadata | Enterprise tool (Looker, Atlan, etc.) | enterprise procurement constraints |

Each boundary has a corresponding ADR explaining the current choice and the explicit conditions under which it should change. See the [ADR index](docs/decisions/README.md).

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
