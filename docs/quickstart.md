# Quick Start

Prerequisites: Docker (Compose plugin), Python 3.13+, `make`.

## 1) Clone and boot

```bash
git clone <repository-url>
cd SoloLakehouse
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
make up
```

`make up` starts the full v2.5 stack including OpenMetadata and Superset.

Durable local state (MinIO, PostgreSQL files, Dagster storage, OpenMetadata MySQL/Elasticsearch) is written under **`docker/data/`** in the repo (bind mounts; see [deployment.md](deployment.md)).

## 2) Verify

```bash
make verify
```

## 3) Run pipeline

```bash
make pipeline
```

## 4) Explore UIs

| Service | URL |
|---------|-----|
| MinIO Console | `http://localhost:9001` |
| Trino | `http://localhost:8080` |
| MLflow | `http://localhost:5000` |
| Dagster | `http://localhost:3000` |
| OpenMetadata | `http://localhost:8585` |
| Superset | `http://localhost:8088` |

Superset default login: `admin / admin`.

## 5) Stop or reset

```bash
make down
make clean
```

For deployment details and troubleshooting, see [deployment.md](deployment.md).
