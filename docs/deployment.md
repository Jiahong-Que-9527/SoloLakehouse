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
make setup
```

`make setup` runs `make init-env` when `.env` is missing, creates `.venv`, installs Python dependencies, pulls container images, starts the Compose stack, bootstraps databases, and waits for service health checks.

### Environment files

`make init-env` is the supported bootstrap:

```bash
make init-env
```

It seeds two files from their committed templates and merges them into `.env`:

| File | Contents | Template | Committed? |
|------|----------|----------|------------|
| `.env.shared` | non-secret configuration (endpoints, bucket names, `RUNTIME_VERSION`) | `.env.shared.example` | gitignored |
| `.env.secrets` | credentials and tokens (`POSTGRES_PASSWORD`, `S3_SECRET_KEY`, `OPENMETADATA_AUTH_TOKEN`) | `.env.secrets.example` | gitignored |
| `.env` | merged result consumed by Compose and the host-side scripts | generated | gitignored |

Do **not** use `cp .env.example .env`. `.env.example` is retained as a legacy
single-file reference; copying it bypasses the v2.9 secrets split that
`make secrets-discipline` enforces. Edit `.env.shared` / `.env.secrets` and
re-run `make init-env` to regenerate `.env`.

The committed template values are local-demo defaults only. Change passwords and secret keys before exposing any service beyond your own machine; production-grade secret management is tracked for v3.

**Upgrading an existing checkout:** if `docker/data/` already holds state, copy your live credentials and `COMPOSE_PROJECT_NAME` from the previous `.env` into `.env.secrets` / `.env.shared` *before* running `make init-env`. Template defaults will not match persisted MinIO credentials, and `make verify` fails with `SignatureDoesNotMatch` until they align.

## 3. Start and verify

```bash
make up
make verify
make health
```

The health dashboard is available at `http://127.0.0.1:8090/health` while `make health` is running.

## 4. Run pipeline

```bash
make demo
```

`make demo` runs `make verify`, the Dagster demo data-flow job, and Trino row-count assertions for Hive Gold and Iceberg Gold. Use `make pipeline` when you explicitly want the full pipeline including MLflow experiment execution.

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

For long-running product entities, keep the same state classes but move
ownership under an entity root such as `/opt/<product_id>/data/`. See
[runtime-state-layout.md](runtime-state-layout.md) for the entity-owned host
layout, `.env` location, and side-by-side upgrade rules.

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
