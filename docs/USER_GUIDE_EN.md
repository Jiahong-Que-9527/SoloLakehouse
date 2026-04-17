# SoloLakehouse User Guide (v2.5)

This guide covers the **single-track v2.5 runtime** only.
Legacy parallel execution paths are archived under `docs/history/`.

## 1. Platform Overview

SoloLakehouse is a locally runnable Lakehouse reference implementation.

Data flow:

ECB/DAX sources -> Bronze -> Silver -> Gold -> MLflow

Default stack:
- MinIO
- PostgreSQL
- Hive Metastore
- Trino (Hive + Iceberg)
- MLflow
- Dagster
- OpenMetadata
- Superset

## 2. Prerequisites

- Docker + Docker Compose plugin
- Python 3.13+
- `make`

Initial setup:

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. Start and Verify

```bash
make up
make verify
```

`make verify` checks MinIO, PostgreSQL, Hive Metastore, Trino, MLflow, Dagster, OpenMetadata, and Superset by default.

## 4. Run Pipeline

```bash
make pipeline
```

This runs Dagster `full_pipeline_job` and is the only supported execution entrypoint.

## 5. Service UIs

| Service | URL |
|---------|-----|
| MinIO Console | `http://localhost:9001` |
| Trino UI | `http://localhost:8080` |
| MLflow UI | `http://localhost:5000` |
| Dagster UI | `http://localhost:3000` |
| OpenMetadata | `http://localhost:8585` |
| Superset | `http://localhost:8088` |

Superset default credentials: `admin / admin`.

## 6. Cleanup

### Safe cleanup (keep volumes)

```bash
make down
```

### Deep cleanup (destructive)

```bash
make clean
docker image prune -f
docker volume prune -f
```

## 7. Troubleshooting

1) `make up` is slow or times out  
- OpenMetadata and Elasticsearch can take extra time during first boot. Re-run `make verify`.

2) `make pipeline` fails  
- Run `make verify` first and confirm Trino, MLflow, and Dagster are healthy.

3) Superset login issues  
- Check `SUPERSET_ADMIN_USERNAME`, `SUPERSET_ADMIN_PASSWORD`, and `SUPERSET_SECRET_KEY` in `.env`.

## 8. Legacy References

Historical context only:
- `docs/history/timeline.md`
- `docs/history/architecture-evolution.md`
- `docs/history/legacy-overview.md`
