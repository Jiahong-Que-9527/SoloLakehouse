# SoloLakehouse

<p align="center">
  <img src="docs/img/slh-brand.svg" width="320" alt="SoloLakehouse">
</p>

<p align="center">
  <i>Minimal internal-style data platform: ingestion, analytics, and ML on the lakehouse.</i>
</p>

## What is this?

SoloLakehouse is a **small but complete Lakehouse reference implementation** built from open-source components. It shows how platforms like Databricks or Snowflake are typically layered — object storage, medallion transforms, SQL, ML tracking.

**This is not a framework.** It is a repo you can read, run, and change. **Development targets [v1.0](docs/roadmap.md):** an eight-layer enterprise-style lakehouse and reliable local deployment. The repo implements a **five-layer core** (ingestion → medallion storage → query → ML) as the foundation for that release.

**Third-party components** (MinIO, PostgreSQL, Hive Metastore, Trino, MLflow, etc.) keep their own licenses; this repo’s license applies to code and docs here.

## Five-layer core

<p align="center">
  <img src="docs/img/SLH_arch_v0.1.svg" width="60%" alt="Five-layer core architecture">
</p>

| Layer | Role |
|-------|------|
| Sources | ECB API + simulated DAX CSV |
| Ingestion | Python collectors, Pydantic, structlog |
| Storage | MinIO, Parquet, Bronze / Silver / Gold |
| Query | Trino + Hive Metastore + PostgreSQL |
| ML | MLflow |

**Details:** [docs/architecture.md](docs/architecture.md) · **Medallion:** [docs/medallion-model.md](docs/medallion-model.md)

### Target — v1.0

![v1.0 target architecture](docs/img/SLH_arch_v1.0.svg)

Eight-layer enterprise-style stack (metadata, observability, user access, etc.): **[docs/roadmap.md](docs/roadmap.md)**.

## Quick start

**Needs:** Docker + Compose, Python 3.11+, `make`.

```bash
git clone <repository-url>
cd SoloLakehouse
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make up
```

- MinIO Console: http://localhost:9001  
- Trino: http://localhost:8080  
- MLflow: http://localhost:5000  

```bash
make verify
make pipeline
```

Full walkthrough: **[docs/quickstart.md](docs/quickstart.md)** · Deploy prerequisites and troubleshooting: **[docs/deployment.md](docs/deployment.md)**

## Design decisions (ADRs)

| ADR | Topic |
|-----|--------|
| [ADR-001](docs/decisions/ADR-001-docker-compose.md) | Docker Compose vs Kubernetes |
| [ADR-002](docs/decisions/ADR-002-trino-vs-duckdb.md) | Trino vs DuckDB |
| [ADR-003](docs/decisions/ADR-003-parquet-vs-delta.md) | Parquet vs Delta Lake |
| [ADR-004](docs/decisions/ADR-004-financial-dataset.md) | ECB + DAX data |
| [ADR-005](docs/decisions/ADR-005-v1-scope.md) | Observability / SQL UI deferred until after the five-service core (see ADR) |

## Documentation index

| Doc | Content |
|-----|---------|
| [docs/README.md](docs/README.md) | All docs |
| [docs/roadmap.md](docs/roadmap.md) | v1.0 target and later versions |
| [docs/EVOLVING_PLAN.md](docs/EVOLVING_PLAN.md) | Detailed implementation tasks |
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
