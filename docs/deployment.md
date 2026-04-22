# Deployment Guide

This guide covers local deployment for the **v2.5 single-track runtime**.

## 1. Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 4 cores | 6+ cores |
| Free RAM | 8 GB | 12+ GB |
| Disk | 10 GB | 20+ GB |

| Software | Version |
|----------|---------|
| Docker Engine | 24.0+ |
| Docker Compose plugin | v2.20+ |
| Python | 3.13+ |
| make | any |

## 2. Setup

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. Start and verify

```bash
make up
make verify
```

## 4. Run pipeline

```bash
make pipeline
```

## 5. Service ports

| Service | Port |
|---------|------|
| MinIO API | 9000 |
| MinIO Console | 9001 |
| PostgreSQL | 5432 |
| Hive Metastore | 9083 |
| Trino | 8080 |
| MLflow | 5000 |
| Dagster | 3000 |
| OpenMetadata | 8585 / 8586 |
| OpenMetadata MySQL | 3307 |
| OpenMetadata Elasticsearch | 9200 / 9300 |
| Superset | 8088 |

## 6. Runtime data on disk

Compose uses **bind mounts** under `docker/data/` in the repository (not Docker named volumes):

| Path | Service |
|------|---------|
| `docker/data/minio` | MinIO object storage |
| `docker/data/postgres` | PostgreSQL cluster files |
| `docker/data/dagster` | Dagster local storage |
| `docker/data/om-mysql` | OpenMetadata MySQL |
| `docker/data/om-elasticsearch` | OpenMetadata Elasticsearch |

`make up` runs `scripts/prepare-docker-data-dirs.sh` to create these directories. They are listed in `.gitignore` (except `docker/data/.gitkeep`).

## 7. Operational cleanup

### Safe cleanup (recommended day-to-day)

Stops containers and removes orphaned containers, but keeps `docker/data/` and images.

```bash
docker compose --env-file .env \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.openmetadata.yml \
  -f docker/docker-compose.superset.yml \
  down --remove-orphans
```

### Deep cleanup (destructive)

`make clean` stops the stack, deletes the `docker/data/*` bind-mount directories, recreates empty dirs, and removes any **legacy** Docker named volumes from older layouts (names like `*_postgres_data`).

```bash
make clean
```

Optional: prune unused images and other dangling volumes not managed by this project:

```bash
docker image prune -f
docker volume prune -f
```

## 8. Troubleshooting

### `make up` times out
- Check Docker resources (CPU/RAM), especially for OpenMetadata + Elasticsearch.
- Re-run `make verify` to identify failing services.

### Superset cannot log in
- Confirm `.env` has `SUPERSET_ADMIN_USERNAME`, `SUPERSET_ADMIN_PASSWORD`, and `SUPERSET_SECRET_KEY`.
- Recreate stack with `make clean && make up`.

### OpenMetadata starts slowly
- First startup includes migration and Elasticsearch warm-up.
- Wait 2-5 minutes before final health verification.

### Pipeline run fails immediately
- Run `make verify` first; ensure Trino, MLflow, and Dagster are all `PASS`.
