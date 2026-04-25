# SoloLakehouse

<p align="center">
  <img src="docs/img/slh-brand.png" width="320" alt="SoloLakehouse">
</p>

<p align="center">
  <i>A production-minded lakehouse reference implementation with a single v2.5 runtime path.</i>
</p>

<p align="center">
  <a href="https://github.com/Jiahong-Que-9527/SoloLakehouse/actions/workflows/test.yml"><img src="https://github.com/Jiahong-Que-9527/SoloLakehouse/actions/workflows/test.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.13%2B-blue.svg" alt="Python 3.13+">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License">
</p>

## Why this might be worth a look

If you've used Databricks or Snowflake and wondered how those pieces fit together, this is the open-source equivalent assembled by hand on one node. You can read the full **Bronze -> Silver -> Gold (Iceberg) -> MLflow** chain end-to-end, see how Dagster assets / sensors / asset checks wire orchestration, and find **16 ADRs** documenting the architecture trade-offs (Trino vs DuckDB, Parquet vs Delta, Compose vs K8s, Iceberg-on-Trino, ...).

There is also a [self-assessment](docs/ASSESSMENT_LAKEHOUSE_DAX_ECB.md) that is honest about where the reference implementation cuts corners (e.g. Iceberg Gold currently rebuilt via DROP+CTAS, Silver transformations in pandas rather than Trino SQL, DAX as static CSV).

This is not a framework or a library. It is one runnable example you can read, fork, and break.

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

Suggested host sizing for Docker runtime:

| Profile | vCPU | Free RAM | Disk (SSD/NVMe) | Notes |
|---------|------|----------|-----------------|-------|
| Minimum | 4 | 8 GB | 40 GB | Can run the full stack, but startup may be slower. |
| Recommended | 6+ | 12+ GB | 80+ GB | Stable for local development and single-user demos. |
| Demo-stable | 8 | 16+ GB | 100+ GB | Better for live demos with multiple UIs open. |

See `docs/deployment.md` for full deployment details and troubleshooting.

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

**CI (GitHub Actions):** on every push and pull request, the [workflow](.github/workflows/test.yml) runs `ruff`, `mypy`, and **unit** `pytest` with a coverage floor (`tests/integration` is excluded). For parity with `make typecheck`, install `requirements-dagster.txt` in your venv. **Integration tests** need the Docker stack: run `make test-integration` (with services up) or the full local gate `make release-check` (`verify` + unit + integration tests) before a release or when changing cross-service behavior.

Cleanup options:

```bash
make down                    # safe: stop stack, keep data under docker/data/
make clean                   # destructive: stop stack, delete docker/data/, remove legacy named volumes
docker image prune -f        # optional: remove unused images
docker volume prune -f       # optional: remove other dangling Docker volumes
```

Runtime state (MinIO, PostgreSQL files, Dagster storage, OpenMetadata MySQL/Elasticsearch) is stored under **`docker/data/`** in the repo (bind mounts), not in Docker-managed named volumes under the engine store.

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

[MIT](LICENSE)
