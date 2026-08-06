# Quick Start

Prerequisites: Docker (Compose plugin), Python 3.13+, Git, and `make`.

## 1) Clone and boot

```bash
git clone <repository-url>
cd SoloLakehouse
make setup
```

`make setup` runs `make init-env` if `.env` is missing, creates `.venv` if needed, installs Python dependencies, pulls images, and starts the full v2.5 stack including OpenMetadata and Superset.

`make init-env` seeds `.env.shared` (non-secret configuration) and `.env.secrets`
(credentials and tokens) from their committed templates and merges both into
`.env`. Do **not** use `cp .env.example .env` — that bypasses the v2.9 secrets
split. See [deployment.md](deployment.md#environment-files).

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

## 6) Product entity deployments (optional)

The steps above run the **local finance reference** (`PRODUCT_ID=sololakehouse`).
To deploy an independently operated entity (for example FinLakehouse on a VPS),
use an entity-specific `.env`, follow the
[product entity contract](product-entity-contract.md), and see
[deployment.md — product entity deployments](deployment.md#7-product-entity-deployments-optional)
or the [FinLakehouse deployment guide](finlakehouse-deployment-guide.md).

Changing `.env` isolates identity and storage; switching to another data domain
requires pipeline changes in the entity clone — see [`task.md`](../task.md)
(design reference; roadmap D2 deferred).
