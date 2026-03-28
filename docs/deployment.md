# Deployment guide

Deploy SoloLakehouse on your machine: MinIO, PostgreSQL, Hive Metastore, Trino, MLflow, Dagster. For a short command sequence after prerequisites are met, see **[quickstart.md](quickstart.md)**.

---

## 1. Hardware

| Resource | Minimum | Recommended |
|----------|---------|---------------|
| CPU | 2 cores | 4+ |
| RAM (free) | 4 GB | 8+ GB |
| Disk | 5 GB | 10+ GB |
| Network | Yes (images + ECB API for pipeline) | — |

Eight containers in v2 mode (7 core services + minio-init helper); idle RAM is typically higher than v1 and depends on host limits.

---

## 2. Software

| Software | Version | Purpose |
|----------|---------|---------|
| Docker Engine | 24.0+ | Runtime |
| Docker Compose | v2.20+ (plugin) | Orchestration |
| Python | 3.11+ | Pipeline scripts |
| make | any | `Makefile` tasks |

```bash
docker --version
docker compose version
python3 --version
make --version
```

### Operating systems

| OS | Notes |
|----|--------|
| Linux (e.g. Ubuntu 22.04+, Debian 12+) | Recommended |
| macOS 13+ | Docker Desktop |
| Windows 11 + WSL2 | Run commands inside WSL |

---

## 3. Deploy

### 3.1 Clone

```bash
git clone <repository-url>
cd SoloLakehouse
```

### 3.2 Environment

```bash
cp .env.example .env
```

Defaults are for local dev; changing `.env` updates services that load these variables.

### 3.3 Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`make` commands prefer `.venv/bin/python` automatically when that virtual environment exists.

### 3.4 Start services

```bash
make up
```

`make up` starts services, ensures the required PostgreSQL databases exist (`hive_metastore`, `mlflow`, `dagster_storage`), and waits until health checks pass (up to 5 minutes). It also runs `minio-init` for buckets `sololakehouse` and `mlflow-artifacts`.

For first-time setup, you can use one command:

```bash
make setup
```

This checks Docker, ensures `.env` exists, pulls images, starts services, and waits for readiness.

### 3.5 Verify

```bash
make verify
```

To include the optional OpenMetadata stack in validation:

```bash
make verify-openmetadata
```

### 3.6 Pipeline and UIs

Run the demo and open MinIO / Trino / MLflow: **[quickstart.md](quickstart.md)** (pipeline step table, SQL examples, `make down` / `make clean`).

For v2, default execution is Dagster (`make pipeline`).  
For v1-compatible behavior, use:

```bash
make pipeline PIPELINE_MODE=v1
# or
make pipeline-v1
```

---

## 4. Ports

| Service | Port | Purpose |
|---------|------|---------|
| MinIO API | 9000 | S3 API |
| MinIO Console | 9001 | Web UI |
| PostgreSQL | 5432 | Metastore + MLflow DB |
| Hive Metastore | 9083 | Thrift |
| Trino | 8080 | HTTP + UI |
| MLflow | 5000 | HTTP |
| Dagster Webserver | 3000 | UI + orchestration endpoint |

Override host ports in `.env` if needed (e.g. `PG_PORT`, `MINIO_API_PORT`). `verify-setup.py` and pipeline scripts should read the same variables.

---

## 5. Stop and reset

```bash
make down      # keep volumes
make clean     # remove volumes (destructive)
```

---

## 6. Tests

```bash
make test
```

Unit tests use mocks; Docker is not required.

For a fuller local release-style check with Docker services running:

```bash
make release-check
```

---

## Troubleshooting

Commands assume the **repository root** (contains `Makefile`, `docker/`, `scripts/`).

### 1. `hive-metastore` fails to start

Root cause: PostgreSQL is not ready yet.

Fix:
```bash
make clean && make up
```

If you intentionally kept volumes and only the expected databases are missing, `make up` now auto-creates them before readiness checks.

### 2. Trino reports "catalog not available"

Root cause: Hive Metastore is still initializing.

Fix:
1. Wait about 60 seconds.
2. Re-run:
```bash
make verify
```

### 3. ECB API timeout during pipeline run

Root cause: ECB API can be rate-limited or temporarily slow.

Fix:
```bash
make pipeline
```
Retrying is usually sufficient. If needed, test legacy compatibility path:

```bash
make pipeline PIPELINE_MODE=v1
```

### 4. MinIO "bucket already exists" error

Root cause: bucket bootstrap re-runs.

Fix: safe to ignore. `minio-init` is idempotent.

### 5. MLflow UI shows no experiments

Root cause: no experiment runs have been logged yet.

Fix:
```bash
make pipeline
```
The `ecb_dax_impact` experiment is created automatically during the run.

### 6. Iceberg Gold DDL fails in Trino

Root cause: staging Parquet is missing or Hive external table metadata is stale.

Fix:
1. Confirm `gold/rate_impact_features/ecb_dax_features.parquet` exists in MinIO after `make pipeline`.
2. Re-run the Gold step so `ingestion.trino_sql.register_gold_tables_trino` can refresh `hive.gold` + `iceberg.gold`.

### 7. OpenMetadata slow to start or OOM

Root cause: Elasticsearch + OpenMetadata JVM need RAM.

Fix: start only when needed (`make up-openmetadata`), increase Docker memory, or stop other stacks. First-time migration (`om-migrate`) can take several minutes.

---

## 8. What’s next

- **Architecture & ADRs:** [architecture.md](architecture.md), [decisions/](decisions/)
- **Roadmap:** [roadmap.md](roadmap.md)
- **Contribute:** [contributing.md](contributing.md)
