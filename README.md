# SoloLakehouse

<p align="center">
  <img src="docs/img/slh-brand.png" width="320" alt="SoloLakehouse">
</p>

<p align="center">
  <i>A production-minded lakehouse reference implementation with a single v2.5 runtime path.</i>
</p>

## What this project is

SoloLakehouse is a runnable Lakehouse reference implementation built with open-source components.
It is not a framework and not a library.

The active runtime is **v2.5 only**:
- Dagster orchestration
- Trino + Hive Metastore + Iceberg Gold
- MLflow tracking
- OpenMetadata and Superset included in the default stack

Legacy version behavior (v1/v2 parallel execution) is archived in `docs/history/`.

## Runtime stack (v2.5 baseline)

| Layer | Component |
|-------|-----------|
| Object storage | MinIO |
| Metadata DB | PostgreSQL |
| Metastore | Hive Metastore |
| Query engine | Trino (`hive` + `iceberg`) |
| Orchestration | Dagster |
| ML tracking | MLflow |
| Metadata catalog | OpenMetadata |
| BI / SQL UI | Superset |

Architecture diagram: [docs/img/SLHv2.5-architecture.jpg](docs/img/SLHv2.5-architecture.jpg)

## Quick start

Requirements: Docker + Compose plugin, Python 3.13+, `make`.

```bash
git clone https://github.com/Jiahong-Que-9527/SoloLakehouse.git
cd SoloLakehouse
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make setup
```

Run and validate:

```bash
make verify
make pipeline
```

Default service URLs:
- MinIO Console: `http://localhost:9001`
- Trino UI: `http://localhost:8080`
- MLflow UI: `http://localhost:5000`
- Dagster UI: `http://localhost:3000`
- OpenMetadata UI: `http://localhost:8585`
- Superset UI: `http://localhost:8088`

## Common commands

```bash
make up
make verify
make pipeline
make down
make clean
make test
make lint
make typecheck
```

Cleanup options:

```bash
make down                    # safe: stop stack, keep volumes
make clean                   # destructive: stop and remove project volumes
docker image prune -f        # optional: remove unused images
docker volume prune -f       # optional: remove dangling volumes
```

## Documentation

- Main docs index: [docs/README.md](docs/README.md)
- User guide (ZH): [docs/USER_GUIDE.md](docs/USER_GUIDE.md)
- User guide (EN): [docs/USER_GUIDE_EN.md](docs/USER_GUIDE_EN.md)
- Deployment and troubleshooting: [docs/deployment.md](docs/deployment.md)
- Roadmap: [docs/roadmap.md](docs/roadmap.md)
- Historical versions and migration records: [docs/history/README.md](docs/history/README.md)

## ADRs

See [docs/decisions/README.md](docs/decisions/README.md) for the full Architecture Decision Record index.

## License

MIT
