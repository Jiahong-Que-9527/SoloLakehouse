# Deployment guide

Deploy SoloLakehouse on your machine: MinIO, PostgreSQL, Hive Metastore, Trino, MLflow. For a short command sequence after prerequisites are met, see **[quickstart.md](quickstart.md)**.

---

## 1. Hardware

| Resource | Minimum | Recommended |
|----------|---------|---------------|
| CPU | 2 cores | 4+ |
| RAM (free) | 4 GB | 8+ GB |
| Disk | 5 GB | 10+ GB |
| Network | Yes (images + ECB API for pipeline) | — |

About five containers; idle RAM often ~2–3 GB on an 8 GB host.

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

### 3.4 Start services

```bash
make up
```

Pulls/builds images (first run may take several minutes), starts services, runs `minio-init` for buckets `sololakehouse` and `mlflow-artifacts`.

### 3.5 Verify

```bash
make verify
```

### 3.6 Pipeline and UIs

Run the demo and open MinIO / Trino / MLflow: **[quickstart.md](quickstart.md)** (pipeline step table, SQL examples, `make down` / `make clean`).

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

---

## Troubleshooting

Commands assume the **repository root** (contains `Makefile`, `docker/`, `scripts/`).

### 1. `hive-metastore` fails to start

Root cause: PostgreSQL is not ready yet.

Fix:
```bash
make clean && make up
```

### 2. Trino reports "catalog not available"

Root cause: Hive Metastore is still initializing.

Fix:
1. Wait about 60 seconds.
2. Re-run:
```bash
make verify
```

### 3. ECB API timeout during `make pipeline`

Root cause: ECB API can be rate-limited or temporarily slow.

Fix:
```bash
make pipeline
```
Retrying is usually sufficient.

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

---

## 8. What’s next

- **Architecture & ADRs:** [architecture.md](architecture.md), [decisions/](decisions/)
- **Roadmap:** [roadmap.md](roadmap.md)
- **Contribute:** [contributing.md](contributing.md)
