# SoloLakehouse User Guide

> From download to full platform walkthrough — everything you need to run a production-minded Lakehouse on your local machine.

---

## Table of Contents

1. [What is SoloLakehouse](#1-what-is-sololakehouse)
2. [Prerequisites](#2-prerequisites)
3. [Installation and Startup](#3-installation-and-startup)
4. [Verifying the Platform](#4-verifying-the-platform)
5. [v1 Walkthrough: Linear Script Pipeline](#5-v1-walkthrough-linear-script-pipeline)
6. [v2 Walkthrough: Dagster Asset Orchestration](#6-v2-walkthrough-dagster-asset-orchestration)
7. [Exploring the Platform UIs](#7-exploring-the-platform-uis)
8. [Command Reference](#8-command-reference)
9. [v3 Roadmap Preview](#9-v3-roadmap-preview)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. What is SoloLakehouse

SoloLakehouse is a **fully runnable Lakehouse reference implementation** that uses open-source components to demonstrate the core layered architecture behind platforms like Databricks and Snowflake.

**It is not a framework or a library.** It is a real engineering repository you can clone, run, read, and modify.

### Platform stack

| Layer | Component | Role |
|-------|-----------|------|
| Object storage | MinIO | S3-compatible store for all Parquet data |
| Metadata | Hive Metastore + PostgreSQL | Table registration and SQL addressability |
| Query engine | Trino | Cross-layer SQL queries |
| ML tracking | MLflow | Experiment parameters, metrics, and model artifacts |
| Orchestration | Dagster | Asset-based pipeline scheduling and governance (v2) |

### Data flow

```
ECB API  (European Central Bank interest rates)
DAX CSV  (German stock index daily data)
        ↓
   Bronze layer  (raw Parquet, immutable, partitioned by date)
        ↓
   Silver layer  (cleaned, typed, derived fields, deduplicated)
        ↓
   Gold layer    (ECB event-study feature table)
        ↓
   MLflow        (XGBoost / LightGBM experiments)
```

### Version status

| Version | Status | Core capability |
|---------|--------|----------------|
| **v1.0** | ✅ Delivered | Five-service platform baseline, end-to-end linear pipeline |
| **v2.0** | ✅ Current | Dagster asset orchestration, schedule / sensor / asset checks |
| **v3.0** | 📋 Planned | Kubernetes, Terraform, secrets governance, SLO-driven observability |

---

## 2. Prerequisites

### 2.1 Hardware

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| Free RAM | 4 GB | 8+ GB |
| Disk space | 5 GB | 10+ GB |
| Network | Required (image pull + ECB API) | — |

> v2 runs 8 containers. Idle memory usage is typically 2–3 GB.

### 2.2 Software

| Software | Version | Check |
|----------|---------|-------|
| Docker Engine | 24.0+ | `docker --version` |
| Docker Compose | v2.20+ (plugin) | `docker compose version` |
| Python | 3.11+ | `python3 --version` |
| make | any | `make --version` |

### 2.3 Operating systems

| OS | Support |
|----|---------|
| Linux (Ubuntu 22.04+ / Debian 12+) | ✅ Recommended |
| macOS 13+ (Docker Desktop) | ✅ Supported |
| Windows 11 + WSL2 | ✅ Run all commands inside WSL |

---

## 3. Installation and Startup

### 3.1 Clone from GitHub

```bash
git clone https://github.com/<your-username>/SoloLakehouse.git
cd SoloLakehouse
```

### 3.2 Configure environment variables

```bash
cp .env.example .env
```

`.env` contains default local development credentials for all services. **No changes are needed for a local walkthrough.** Edit specific variables only if you have port conflicts.

### 3.3 Set up Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate        # Linux / macOS
# Windows WSL: same command
pip install -r requirements.txt
```

### 3.4 Start the platform

**Recommended for first run: `make setup`** — checks Docker, ensures `.env` exists, pulls images, starts services, and waits for all health checks to pass.

```bash
make setup
```

For subsequent runs (images already present):

```bash
make up
```

`make up` waits until every service health check passes, then prints:

```
SoloLakehouse is ready.
  MinIO Console:  http://localhost:9001
  Trino UI:       http://localhost:8080
  MLflow UI:      http://localhost:5000
  Dagster UI:     http://localhost:3000
  (Optional OpenMetadata: make up-openmetadata)
  (Optional Superset:    make up-superset)
```

> First-time image pull takes 5–10 minutes. Subsequent starts take 1–2 minutes.

---

## 4. Verifying the Platform

```bash
make verify
```

When all services are healthy:

```
Service          Status  Detail
---------------- ------- ----------------------------
MinIO            PASS    Buckets: sololakehouse, mlflow-artifacts
PostgreSQL       PASS    Databases: dagster_storage, hive_metastore, mlflow
Hive Metastore   PASS    TCP port 9083 open
Trino            PASS    Running, not starting
MLflow           PASS    HTTP 200
Dagster          PASS    HTTP 200 /server_info
```

If any service shows `FAIL` or `TIMEOUT`, see [Section 10: Troubleshooting](#10-troubleshooting).

If you enabled the optional add-ons, you can also run:

```bash
make verify-openmetadata
make verify-superset
```

---

## 5. v1 Walkthrough: Linear Script Pipeline

v1 is the foundational execution path — a clearly structured six-step data engineering pipeline that runs sequentially without any external orchestration service.

### 5.1 Run the v1 pipeline

```bash
make pipeline-v1
```

Equivalent:

```bash
make pipeline PIPELINE_MODE=v1
```

### 5.2 What each step does

| Step | Name | What happens |
|------|------|-------------|
| 1 | ECB Ingestion | Fetches ECB MRO rate data from the ECB SDW REST API; validates with Pydantic; writes to Bronze |
| 2 | DAX Ingestion | Reads `data/sample/dax_daily_sample.csv`; validates; writes to Bronze |
| 3 | ECB Bronze → Silver | Type cleanup, forward-fill, derives `rate_change_bps` |
| 4 | DAX Bronze → Silver | Filters weekends, derives `daily_return` |
| 5 | Silver → Gold | Anchors on ECB rate decision dates; joins ±5 trading days of DAX data; builds event-study feature table |
| 6 | ML Experiment | Runs XGBoost / LightGBM hyperparameter combinations; logs results to MLflow |

Successful output looks like:

```
[Step 1/6] ECB Ingestion ✓  (valid=847, rejected=0)
[Step 2/6] DAX Ingestion ✓  (valid=1305, rejected=0)
[Step 3/6] ECB Bronze → Silver ✓
[Step 4/6] DAX Bronze → Silver ✓
[Step 5/6] Silver → Gold ✓
[Step 6/6] ML Experiment ✓  best_run_id=<mlflow-run-id>
```

### 5.3 Exploring the output

**MinIO — browse layered data files**

Open http://localhost:9001. Log in with `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` from `.env` (defaults: `sololakehouse` / `sololakehouse123`).

Browse the bucket structure:

```
sololakehouse/
  bronze/
    ecb_rates/ingestion_date=YYYY-MM-DD/
    dax_daily/ingestion_date=YYYY-MM-DD/
    rejected/source=ECB/ingestion_date=YYYY-MM-DD/
  silver/
    ecb_rates_cleaned/
    dax_daily_cleaned/
  gold/
    ecb_dax_features/
```

**Trino — query the Gold layer**

```bash
docker exec -it slh-trino trino
```

Inside the Trino CLI:

```sql
-- List available catalogs and schemas
SHOW CATALOGS;
SHOW SCHEMAS IN hive;

-- Query the Gold feature table
SELECT
    event_date,
    rate_change_bps,
    dax_return_1d,
    dax_return_5d
FROM hive.gold.ecb_dax_features
ORDER BY event_date
LIMIT 10;
```

Exit the CLI: `quit`

**MLflow — view ML experiments**

Open http://localhost:5000, navigate to experiment **ecb_dax_impact**:
- Model type (xgboost / lightgbm) and hyperparameters per run
- Validation RMSE / MAE metrics
- Best run ID and artifact path

### 5.4 Engineering characteristics in v1

v1 is built with production-minded patterns even at the script level:

- **Incremental ingestion** — checks whether today's partition already exists; skips re-ingestion if so
- **Force re-run** — `make pipeline ARGS="--force"` bypasses the incremental check
- **Automatic retry** — ECB API calls retry up to 3 times; raises `CollectorUnavailableError` on exhaustion
- **Rejected records** — records that fail Pydantic validation are written to `bronze/rejected/` rather than dropped
- **Quality checks** — Bronze layer validates no future dates, date continuity, and schema completeness

---

## 6. v2 Walkthrough: Dagster Asset Orchestration

v2 adds **platform semantics** on top of v1's data logic. Data is no longer a by-product of scripts — it is explicitly defined, dependency-aware, and governable as **software-defined assets (SDA)**.

### 6.1 Run the v2 pipeline

```bash
make pipeline
```

This is the v2 default path. It executes `full_pipeline_job` inside the Dagster container.

Successful output ends with:

```
RUN_SUCCESS
```

### 6.2 Asset dependency graph

v2 defines 6 software-defined assets with an explicit dependency structure:

```
ecb_bronze ──────┐
                 ├──► ecb_silver ──┐
                 │                 ├──► gold_features ──► ml_experiment
dax_bronze ──────┘                 │
                 ├──► dax_silver ──┘
```

Each asset in the Dagster UI shows:
- Materialization history and output metadata (row counts, paths, durations)
- Option to re-materialize individually without re-running the full graph
- Upstream and downstream dependency visualization

### 6.3 Using the Dagster UI

Open http://localhost:3000

**Asset Graph**

Home → **Assets** → **Asset Graph**

Shows all 6 asset nodes and their dependency edges. Click any asset node to see:
- Last materialization timestamp and status
- Output metadata (row counts, storage paths)
- Upstream / downstream relationships

**Trigger a full pipeline run manually**

1. Click **Materialize all** in the top-right corner
2. Confirm in the dialog
3. Navigate to **Runs** to monitor execution progress

**View run logs**

Runs → click any run → expand each step to view structured logs (structlog format, key-value pairs)

**Re-materialize a single asset**

Use case: one step failed, or upstream data was updated and only a specific layer needs refreshing.

1. Click the target asset (e.g. `gold_features`)
2. Click **Materialize** in the right panel
3. Dagster automatically resolves dependencies and runs only what is needed

### 6.4 Scheduling and automation

**Daily schedule**

Navigate to **Deployments → Schedules**, find `daily_pipeline_schedule`:
- Cron: `0 6 * * 1-5` (weekdays at UTC 06:00)
- Off by default; click the **Running** toggle to enable

**Data freshness sensor**

Navigate to **Deployments → Sensors**, find `ecb_data_freshness_sensor`:
- Runs every 30 minutes
- If the latest ECB Bronze partition is more than 48 hours old, automatically triggers `ecb_bronze` re-materialization

**Gold layer asset check**

Navigate to **Assets → Asset Checks**, find `gold_features_min_rows_check`:
- Runs automatically after every `gold_features` materialization
- Verifies row count ≥ 10; fewer rows indicates a potential upstream data problem

### 6.5 v1 vs v2 comparison

| Dimension | v1 (legacy script) | v2 (Dagster) |
|-----------|-------------------|--------------|
| Trigger | `make pipeline-v1` | `make pipeline` |
| Execution view | Sequential step logs | Asset dependency graph + UI |
| Failure recovery | Re-run from scratch or skip manually | Re-materialize individual assets |
| Scheduling | None | Daily cron + data freshness sensor |
| Data quality | Script log output | Asset checks (stateful, traceable) |
| Best for | Quick local validation, fallback path | Day-to-day operations, governance demos |

The two paths produce **identical data** — the same Bronze, Silver, and Gold output. v1 is retained as a long-term fallback for v2.

---

## 7. Exploring the Platform UIs

### 7.1 MinIO Console

**URL:** http://localhost:9001
**Login:** `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` from `.env` (defaults: `sololakehouse` / `sololakehouse123`)

What you can do:
- Browse Bronze / Silver / Gold Parquet files
- Download individual Parquet files for local inspection
- Inspect the `mlflow-artifacts` bucket (MLflow model files)
- Review rejected records under `bronze/rejected/`

### 7.2 Trino Web UI + CLI

**Web UI:** http://localhost:8080 — read-only; shows query history and cluster status

**CLI:**

```bash
docker exec -it slh-trino trino
```

Useful queries:

```sql
-- List all schemas
SHOW SCHEMAS IN hive;

-- Inspect the Gold table schema
DESCRIBE hive.gold.ecb_dax_features;

-- Event study: DAX reaction to ECB rate hikes
SELECT
    event_date,
    rate_change_bps,
    ROUND(dax_return_5d, 2) AS dax_5d_return_pct
FROM hive.gold.ecb_dax_features
WHERE rate_change_bps > 0
ORDER BY event_date;

-- View cleaned ECB rates in Silver
SELECT * FROM hive.silver.ecb_rates_cleaned LIMIT 5;
```

### 7.3 MLflow UI

**URL:** http://localhost:5000

Navigation:
1. Click experiment **ecb_dax_impact** in the left sidebar
2. Sort runs by `val_rmse` ascending to find the best model
3. Click any run to inspect:
   - **Parameters:** `n_estimators`, `max_depth`, `learning_rate`, model type
   - **Metrics:** `val_rmse`, `val_mae`, training duration
   - **Artifacts:** model files (stored in MinIO `mlflow-artifacts` bucket)

### 7.4 Dagster UI

**URL:** http://localhost:3000

Page reference:

| Page | Path | Purpose |
|------|------|---------|
| Asset Graph | Assets → Asset Graph | Visualize asset dependencies |
| Runs | Runs | Execution history, logs, step durations |
| Schedules | Deployments → Schedules | Manage the daily schedule |
| Sensors | Deployments → Sensors | Manage the freshness sensor |
| Asset Checks | Assets → Asset Checks | Review data quality check results |

### 7.5 Superset UI (optional)

**Start command:**

```bash
make up-superset
```

**URL:** http://localhost:8088  
**Login:** default `admin / admin`

After the first startup, Superset pre-creates two Trino connections:

- `trino_iceberg_gold`
- `trino_hive_default`

Recommended demo entry points:

- Use `trino_iceberg_gold` for `iceberg.gold.ecb_dax_features_iceberg`
- Use `trino_hive_default` for `hive.gold.ecb_dax_features`
- Use SQL Lab or Chart Builder to visualize Gold features quickly

---

## 8. Command Reference

### Platform lifecycle

```bash
make setup          # First run: check Docker → ensure .env → pull images → start → wait
make up             # Start all services (images already present)
make verify         # Check health of all 6 services
make up-openmetadata # Optional: start OpenMetadata
make verify-openmetadata # Optional: validate OpenMetadata
make up-superset    # Optional: start Superset
make verify-superset # Optional: validate Superset
make down           # Stop services (data volumes preserved)
make clean          # Stop services and delete all volumes (destructive)
```

### Pipeline execution

```bash
make pipeline                              # v2 default: Dagster full_pipeline_job
make pipeline-v1                           # v1 legacy: linear script
make pipeline PIPELINE_MODE=v1             # Same as above
make pipeline ARGS="--force"               # v1: force re-ingest, bypass incremental check
make pipeline PIPELINE_MODE=v2 DAGSTER_JOB=full_pipeline_job  # Explicit Dagster job
```

### Development tools

```bash
make test           # Run all unit tests (no Docker required)
make test-cov       # Tests with coverage report
make lint           # ruff code check
make typecheck      # mypy type check
make dagster-ui     # Open Dagster UI in browser (:3000)
```

### Trino access

```bash
docker exec -it slh-trino trino      # Enter Trino CLI
```

---

## 9. v3 Roadmap Preview

v2 answered: *how do you operate this platform?*
v3 answers: *how do you make this platform production-capable?*

### Planned priorities

| Priority | Scope |
|----------|-------|
| **Infrastructure** | Kubernetes + Helm + Terraform to replace Docker Compose as the deployment foundation |
| **Multi-environment** | `dev → staging → production` promotion chain with explicit validation gates and rollback standards |
| **Security governance** | Secrets lifecycle (replacing static `.env`), least-privilege access model, audit logging |
| **Observability** | SLO definitions, metrics instrumentation, alert rules, dashboards, incident runbooks |
| **Data governance** | Governance contracts for Gold and critical Silver outputs: `data_owner`, `refresh_sla`, `quality_class` |
| **ML experiment governance** | Reproducible training/evaluation contracts, artifact lineage, cross-environment consistency |

### Explicitly not in the v3 **default delivery** scope

The following are intentionally **not** default v3 productionization goals (see [roadmap.md](roadmap.md)):

- Kafka / Flink (stream processing)
- Mandatory migration to OpenMetadata / DataHub (unified enterprise catalog)
- Mandatory wholesale replacement of storage with Delta Lake / Iceberg everywhere
- Online model serving platform
- Keycloak-class end-user identity system
- Superset / FastAPI

**v2.5 reference extension (implemented in this repo):** Gold is available as **Apache Iceberg** (Trino `iceberg` catalog). **OpenMetadata** is optional (`make up-openmetadata`, UI on port 8585), and **Superset** is also optional (`make up-superset`, UI on port 8088) for SQL exploration and dashboard demos. This does not contradict v3 guardrails: v2.5 is an educational/reference add-on; v3 still does not require these optional UIs.

These may be introduced in future versions when driven by a concrete use case — not added speculatively.

### Platform suitability

| Stage | Suitable for |
|-------|-------------|
| v2 (now) | Small internal data teams, MVP-grade internal platforms, low-to-moderate batch workloads |
| v3 (planned) | Teams with compliance requirements, multi-environment HA needs, near-production internal platforms |

---

## 10. Troubleshooting

### A service shows FAIL or TIMEOUT in `make verify`

**hive-metastore FAIL**
Cause: Hive Metastore started before PostgreSQL was fully ready.
Fix:
```bash
make clean && make up
```

**Trino FAIL — "catalog not available"**
Cause: Hive Metastore is still initializing.
Fix: Wait 60 seconds, then re-run `make verify`.

**Dagster FAIL**
Cause: Dagster webserver has a 60-second `start_period`; may still be starting.
Fix: Wait 90 seconds, then re-run `make verify`. If it persists:
```bash
docker logs slh-dagster-webserver --tail 50
```

**MLflow FAIL**
Cause: Usually a PostgreSQL connectivity issue during startup.
Fix: `make clean && make up`

---

### `make pipeline` errors: "Error: No such container: slh-dagster-webserver"

Cause: Dagster container is not running.
Fix:
```bash
make up           # restart all services
make verify       # confirm Dagster shows PASS
make pipeline     # then run the pipeline
```

---

### ECB API timeout during pipeline run

Cause: The ECB SDW API is occasionally slow or rate-limited.
Fix:
```bash
make pipeline     # retry — automatic retries are built in
```

If timeouts persist, switch to v1 for debugging:
```bash
make pipeline-v1
```

---

### Pipeline ran but `SELECT * FROM hive.gold.ecb_dax_features` returns no rows

Cause: Trino was not fully ready when the pipeline registered the table.
Fix:
```bash
make verify        # confirm Trino shows PASS
make pipeline      # re-run the pipeline
```

---

### Data is gone after restart

Cause: `make clean` was used — it removes all Docker volumes.
To stop without losing data:
```bash
make down          # preserves volumes
make up            # data is automatically available after restart
```

---

### MinIO "bucket already exists" error

Cause: `minio-init` re-ran bucket creation.
Action: **Safe to ignore.** `minio-init` is idempotent and does not affect your data.

---

### Port conflict on startup

If ports 9000, 9001, 8080, 5000, 3000, or 5432 are already in use, override them in `.env`:

```bash
MINIO_API_PORT=9010
MINIO_CONSOLE_PORT=9011
PG_PORT=5433
```

Then restart:
```bash
make down && make up
```

---

### View container logs

```bash
docker logs slh-minio --tail 30
docker logs slh-postgres --tail 30
docker logs slh-hive-metastore --tail 30
docker logs slh-trino --tail 30
docker logs slh-mlflow --tail 30
docker logs slh-dagster-webserver --tail 30
docker logs slh-dagster-daemon --tail 30
```

---

## Appendix: Service port reference

| Service | Port | Access |
|---------|------|--------|
| MinIO API | 9000 | S3 SDK / CLI |
| MinIO Console | 9001 | Browser |
| PostgreSQL | 5432 | psql / DB client |
| Hive Metastore | 9083 | Thrift (internal) |
| Trino | 8080 | Browser / CLI |
| MLflow | 5000 | Browser |
| Dagster UI | 3000 | Browser |
