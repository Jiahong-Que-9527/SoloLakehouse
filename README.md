# SoloLakehouse

<p align="center">
  <img src="docs/img/slh-brand.png" width="320" alt="SoloLakehouse">
</p>

<p align="center">
  <i>A production-minded lakehouse platform reference: from runnable core pipelines to orchestrated, governance-ready data and ML operations.</i>
</p>

## What is this?

SoloLakehouse is a **small but complete Lakehouse reference implementation** built from open-source components. It shows how platforms like Databricks or Snowflake are typically layered — object storage, medallion transforms, SQL, ML tracking.

**This is not a framework.** It is a repo you can read, run, and change.

**Current status: [v2.0 (current)](docs/roadmap.md)** — orchestration-first platform upgrade with Dagster assets/schedules/checks, while preserving a v1-compatible execution path.

The project now represents:
- **v1 delivered baseline**: five-service lakehouse core (MinIO/PostgreSQL/Hive Metastore/Trino/MLflow)
- **v2 current platform**: Dagster orchestration layer (`dagster-webserver`, `dagster-daemon`) and governance-oriented runtime controls
- **v3 planned scope**: production-capable platform hardening (Kubernetes/Helm/Terraform, promotion/rollback controls, secrets/access governance, SLO-driven observability, Hive-first governance baseline, ML experiment governance)

**Third-party components** (MinIO, PostgreSQL, Hive Metastore, Trino, MLflow, etc.) keep their own licenses; this repo’s license applies to code and docs here.

## Five-layer core

<p align="center">
  <img src="docs/img/SLH_arch_v0.1.png" width="60%" alt="Five-layer core architecture">
</p>

| Layer | Role |
|-------|------|
| Sources | ECB API + simulated DAX CSV |
| Ingestion | Python collectors, Pydantic, structlog |
| Storage | MinIO, Parquet, Bronze / Silver / Gold |
| Query | Trino + Hive Metastore + PostgreSQL |
| ML | MLflow |

**Details:** [docs/architecture.md](docs/architecture.md) · **Medallion:** [docs/medallion-model.md](docs/medallion-model.md)

### Target — v1.0 (delivered)

![v1.0 target architecture](docs/img/SLH_arch_v1.0.png)

Eight-layer enterprise-style stack (metadata, observability, user access, etc.): **[docs/roadmap.md](docs/roadmap.md)**.

### Current runtime — v2 orchestration

- Default pipeline path: **Dagster** (`make pipeline`)
- Compatibility path: **legacy script** (`make pipeline-v1` or `make pipeline PIPELINE_MODE=v1`)
- Orchestration UI: `http://localhost:3000`

## Quick start

**Needs:** Docker + Compose, Python 3.11+, `make`.

```bash
git clone <repository-url>
cd SoloLakehouse
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make setup
```

- MinIO Console: http://localhost:9001  
- Trino: http://localhost:8080  
- MLflow: http://localhost:5000  
- Dagster: http://localhost:3000

`make up` now waits for all services to become healthy before returning.

```bash
make verify
make pipeline
```

Compatibility run (v1-style):

```bash
make pipeline-v1
# or
make pipeline PIPELINE_MODE=v1
```

Full walkthrough: **[docs/quickstart.md](docs/quickstart.md)** · Deploy prerequisites and troubleshooting: **[docs/deployment.md](docs/deployment.md)** · Release steps: **[docs/release.md](docs/release.md)**

## Quick Validation

After `make up`, run:

```bash
make verify
```

Expected output format:

```text
Service          Status  Detail
---------------- ------- ----------------------------
MinIO            PASS    Buckets: sololakehouse, mlflow-artifacts
PostgreSQL       PASS    Databases: hive_metastore, mlflow
Hive Metastore   PASS    TCP port 9083 open
Trino            PASS    Running, not starting
MLflow           PASS    HTTP 200
```

## Common Issues

See troubleshooting guidance in [docs/deployment.md#troubleshooting](docs/deployment.md#troubleshooting).

## Design decisions (ADRs)

| ADR | Topic |
|-----|--------|
| [ADR-001](docs/decisions/ADR-001-docker-compose.md) | Docker Compose vs Kubernetes |
| [ADR-002](docs/decisions/ADR-002-trino-vs-duckdb.md) | Trino vs DuckDB |
| [ADR-003](docs/decisions/ADR-003-parquet-vs-delta.md) | Parquet vs Delta Lake |
| [ADR-004](docs/decisions/ADR-004-financial-dataset.md) | ECB + DAX data |
| [ADR-005](docs/decisions/ADR-005-v1-scope.md) | Observability / SQL UI deferred until after the five-service core |
| [ADR-006](docs/decisions/ADR-006-v2-dagster-orchestration.md) | v2 Dagster orchestration with legacy fallback |
| [ADR index](docs/decisions/README.md) | Full ADR set including v3 governance decisions |

## Documentation index

| Doc | Content |
|-----|---------|
| [docs/README.md](docs/README.md) | All docs |
| [docs/roadmap.md](docs/roadmap.md) | v1.0 target and later versions |
| [docs/v1-to-v2-transition.md](docs/v1-to-v2-transition.md) | v1 delivered baseline, v2 current scope, migration narrative |
| [docs/EVOLVING_PLAN.md](docs/EVOLVING_PLAN.md) | Detailed implementation tasks |
| [docs/governance-v3-matrix.md](docs/governance-v3-matrix.md) | v3 governance capability matrix |
| [docs/v3-governance-navigation.md](docs/v3-governance-navigation.md) | One-page navigation for v3 governance docs |
| [TASKS.md](TASKS.md) | Backlog and ideas |

## Repository layout

```
SoloLakehouse/
├── config/           # Trino, PostgreSQL, MinIO, …
├── docker/           # Compose + Dockerfiles
├── docs/             # Architecture, ADRs, deployment, roadmap
├── ingestion/        # Collectors, schemas, Bronze writes
├── transformations/  # Bronze → Silver → Gold
├── ml/               # Training and evaluation
├── scripts/          # Pipeline and verification
├── tests/
├── data/sample/      # Sample DAX CSV (demo)
├── TASKS.md
├── README.md
└── CLAUDE.md         # Agent / contributor quick reference
```

## Contributing

See **[docs/contributing.md](docs/contributing.md)** (or [CONTRIBUTING.md](CONTRIBUTING.md) in the root).

## License

MIT
