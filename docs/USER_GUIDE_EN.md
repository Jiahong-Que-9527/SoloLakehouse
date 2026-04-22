# SoloLakehouse User Guide (v2.5, Clone-to-Run)

This document is a zero-guess, copy-paste guide for first-time users.  
It covers only the active **v2.5 single-track runtime**. Legacy paths are archived under `docs/history/`.

---

## 0. What You Will Get

After following this guide, you will have a full local lakehouse stack running with:

- MinIO
- PostgreSQL
- Hive Metastore
- Trino (Hive + Iceberg catalogs)
- MLflow
- Dagster
- OpenMetadata
- Superset

Main data flow:

`ECB/DAX sources -> Bronze -> Silver -> Gold -> MLflow`

---

## 1. Prerequisites (Do This First)

### 1.1 Required software

- Docker + Docker Compose plugin
- Python 3.13+
- `make`
- `git`

### 1.2 Verify in terminal

```bash
docker --version
docker compose version
python3 --version
make --version
git --version
```

If Docker is not running, start Docker Desktop / Docker daemon first.

---

## 2. Clone the Repository

```bash
git clone https://github.com/Jiahong-Que-9527/SoloLakehouse.git
cd SoloLakehouse
```

Optional sanity check:

```bash
pwd
ls
```

You should see `Makefile`, `docker/`, `docs/`, `scripts/`, etc.

---

## 3. Create Local Python Environment

Even though core services run in Docker, local helper scripts (such as health checks) run from your Python venv.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional verification:

```bash
which python
python --version
```

`which python` should point to `.../SoloLakehouse/.venv/bin/python`.

---

## 4. Prepare `.env`

```bash
cp .env.example .env
```

Default values are usually enough for local first run.  
If you already have data under `docker/data/` from previous runs, keep DB credentials consistent with that PostgreSQL cluster.

---

## 5. Start the Full Stack

### Recommended for first run

```bash
make setup
```

`make setup` performs:

1. Docker daemon check
2. `.env` bootstrap
3. Image pulling
4. Full service startup + wait for health

First startup may take several minutes, especially for OpenMetadata/Superset-related components.

### Routine startup after first bootstrap

```bash
make up
```

---

## 6. Verify Health (Required Gate)

```bash
make verify
```

Expected: all services show `PASS`:

- MinIO
- PostgreSQL
- Hive Metastore
- Trino
- MLflow
- Dagster
- OpenMetadata
- Superset

If one service is still warming up, wait 10-30 seconds and run `make verify` again.

---

## 7. Open Service UIs

| Service | URL |
|---------|-----|
| MinIO Console | `http://localhost:9001` |
| Trino UI | `http://localhost:8080` |
| MLflow UI | `http://localhost:5000` |
| Dagster UI | `http://localhost:3000` |
| OpenMetadata | `http://localhost:8585` |
| Superset | `http://localhost:8088` |

Superset default credentials: `admin / admin`.

If all pages open after `make verify`, your environment is ready.

---

## 8. Run the Pipeline (Main Workflow)

```bash
make pipeline
```

This executes Dagster `full_pipeline_job` (the canonical v2.5 entrypoint).

After completion, run:

```bash
make verify
```

Then inspect:

- Dagster UI for run status
- MLflow UI for experiment runs
- Trino UI for query activity

---

## 9. Daily Operations

### Stop services safely (keep data)

```bash
make down
```

### Full reset (destructive)

```bash
make clean
docker image prune -f
docker volume prune -f
```

`make clean` removes `docker/data/`, so next startup behaves like a fresh environment.

---

## 10. Troubleshooting (Direct Fixes)

### A) `hive-metastore` fails with PostgreSQL auth error

Symptom: logs include `password authentication failed for user "postgres"`.  
Cause: `.env` password does not match the password stored in the existing PostgreSQL data directory (`docker/data/postgres/`, or a legacy Docker named volume from an older layout).

Fix (keep data):

```bash
docker exec slh-postgres psql -U postgres -d postgres -c "ALTER USER postgres WITH PASSWORD 'postgres';"
make up
make verify
```

### B) MLflow shows `Invalid Host header`

Symptom: opening `http://localhost:5000` returns DNS rebinding warning.  
Cause: allowed host list does not include host header with port.

Fix: update to latest code and rebuild mlflow:

```bash
docker compose --env-file .env -f docker/docker-compose.yml -f docker/docker-compose.openmetadata.yml -f docker/docker-compose.superset.yml up -d --build mlflow
make verify
```

### C) `make up` seems slow

OpenMetadata, Elasticsearch, and Superset can take longer on first startup. Wait and rerun `make verify`.

---

## 11. Minimal Copy-Paste Path

If you only want the fastest deterministic runbook:

```bash
git clone https://github.com/Jiahong-Que-9527/SoloLakehouse.git
cd SoloLakehouse
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
make setup
make verify
make pipeline
```

---

## 12. Legacy References

For historical context only (not active runtime path):

- `docs/history/timeline.md`
- `docs/history/architecture-evolution.md`
- `docs/history/legacy-overview.md`
