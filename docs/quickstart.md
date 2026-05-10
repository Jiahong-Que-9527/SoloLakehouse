# Quick Start

Prerequisites: Docker (Compose plugin), Python 3.13+, Git, and `make`.

## 1) Clone and boot

```bash
git clone <repository-url>
cd SoloLakehouse
make setup
```

`make setup` creates `.env` if needed, creates `.venv` if needed, installs Python dependencies, pulls images, and starts the full v2.5 stack including OpenMetadata and Superset.

Durable local state (MinIO, PostgreSQL files, Dagster storage, OpenMetadata MySQL/Elasticsearch) is written under **`docker/data/`** in the repo (bind mounts; see [deployment.md](deployment.md)).

## 2) Verify

```bash
make verify
```

For a browser health view:

```bash
make health
```

Open `http://127.0.0.1:8090/health`.

## 3) Run the demo path

```bash
make demo
```

`make demo` runs service verification, executes the Dagster demo data-flow job, and checks that both Hive Gold and Iceberg Gold return rows through Trino.

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
