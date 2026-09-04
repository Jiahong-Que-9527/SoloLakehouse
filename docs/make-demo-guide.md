# `make demo` — Detailed Explanation and Manual Execution Guide

This document explains what `make demo` actually does, and how to execute the same steps by hand and confirm each one passes.

Use it when you want to:

- confirm after a cold clone that the data flow really runs
- understand what each step proves before recording a demo
- decompose the flow to find which part failed after `make demo` fails

## 1. Prerequisites

Before running `make demo`, the full stack must be up:

```bash
make setup
```

`make setup` will:

- create `.env`
- create `.venv`
- install Python dependencies
- pull Docker images
- start PostgreSQL, MinIO, Hive Metastore, Trino, Dagster, MLflow, OpenMetadata, and Superset
- wait for all services to become healthy

If this is not your first run, use instead:

```bash
make up
```

Pass criteria:

- exit code `0`
- the terminal ends with `SoloLakehouse is ready.`
- `make verify` reports `PASS` for every service

## 2. What `make demo` does

In the Makefile, `make demo` is equivalent to three steps:

```makefile
demo:
	$(MAKE) verify
	$(MAKE) pipeline DAGSTER_JOB=demo_data_flow_job
	$(PYTHON) scripts/verify-demo.py
```

In plain terms:

1. confirm every service is healthy
2. execute `demo_data_flow_job` through Dagster
3. query the Gold table through Trino and confirm it has data

`make demo` deliberately does not run the full `full_pipeline_job`, because that also trains MLflow experiments. The demo gate exists to prove the core data flow quickly: ECB + market leg → Bronze → Silver → Gold → Trino.

> **Layer 1 target (D4):** the market leg is **live EWG via Alpha Vantage**; `data/sample/dax_daily_sample.csv` is **retired** and must not be documented or implemented as a fallback. Until `L4` lands, asset names and tables may still say `dax_*` and read the legacy CSV — treat that as implementation lag only.

## 3. One-command execution

Recommended:

```bash
make demo
```

On success you should see three kinds of evidence.

First — service health checks:

```text
Service          Status  Detail
---------------- ------- ----------------------------
MinIO            PASS
PostgreSQL       PASS
Hive Metastore   PASS
Trino            PASS
MLflow           PASS
Dagster          PASS
Dagster S3 creds PASS
OpenMetadata     PASS
Superset         PASS
```

Second — the Dagster job succeeds:

```text
RUN_SUCCESS - Finished execution of run for "demo_data_flow_job".
```

Third — the Gold SQL assertion succeeds:

```text
Demo check      Rows  Status
--------------- ----- ------
Iceberg Gold    53    PASS
```

The row count need not always equal `53`, but it must be greater than `0`. It changes as the data window changes.

## 4. Manual execution: decomposing `make demo`

To run the steps individually rather than through `make demo`:

### 4.1 Service health check

```bash
make verify
```

This runs:

```bash
.venv/bin/python scripts/verify-setup.py
```

It checks:

- MinIO API availability, and that the configured data, audit, and MLflow artifact buckets exist
- PostgreSQL connectivity and the presence of the required databases
- Hive Metastore port 9083 connectivity
- Trino `/v1/info` health
- MLflow `/health`
- Dagster `/server_info`
- presence of S3 / MLflow environment variables inside the Dagster container
- OpenMetadata API health
- Superset `/health`

Pass criteria:

- every line reads `PASS`
- exit code `0`

If it fails, do not continue to the pipeline. Check the logs for the failing service first:

```bash
docker logs --tail 200 slh-trino
docker logs --tail 200 slh-dagster-webserver
docker logs --tail 200 slh-hive-metastore
```

### 4.2 Execute the demo data-flow job

```bash
make pipeline DAGSTER_JOB=demo_data_flow_job
```

This enters the Dagster container and runs:

```bash
docker compose --env-file .env \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.openmetadata.yml \
  -f docker/docker-compose.superset.yml \
  exec dagster-webserver \
  dagster job execute \
  -f /app/dagster/definitions.py \
  -j demo_data_flow_job
```

`demo_data_flow_job` contains these Dagster assets:

| Asset | Role | Output |
|---|---|---|
| `ecb_bronze` | Fetch and validate ECB rate data | `iceberg.bronze.ecb_rates` (append) |
| `dax_bronze` | Read and validate DAX daily data | `iceberg.bronze.dax_daily` (append) |
| `ecb_silver` | Clean the ECB Bronze data | `iceberg.silver.ecb_rates_cleaned` (overwrite) |
| `dax_silver` | Clean the DAX Bronze data | `iceberg.silver.dax_daily_cleaned` (overwrite) |
| `gold_features` | Join ECB/DAX and build event-study features | `iceberg.gold.ecb_dax_features` (overwrite) |

It also runs `gold_features_min_rows_check` to confirm the Gold features contain enough event rows.

Pass criteria:

```text
RUN_SUCCESS - Finished execution of run for "demo_data_flow_job".
```

Key log lines:

```text
ecb_bronze - STEP_SUCCESS
dax_bronze - STEP_SUCCESS
ecb_silver - STEP_SUCCESS
dax_silver - STEP_SUCCESS
gold_features - STEP_SUCCESS
Asset check 'gold_features_min_rows_check' ... passed
```

If it fails, the Dagster UI gives a clearer picture:

```text
http://localhost:3000
```

Open the most recent `demo_data_flow_job` run and find the first red step.

### 4.3 Verify the Gold table is queryable

```bash
.venv/bin/python scripts/verify-demo.py
```

This queries through Trino:

```sql
SELECT count(*) AS total_rows
FROM iceberg.gold.ecb_dax_features;
```

Pass criteria:

```text
Demo check      Rows  Status
--------------- ----- ------
Iceberg Gold    <n>   PASS
```

where `<n>` must be greater than `0`.

## 5. Fully manual execution: bypassing `make demo`

To bypass the Makefile entirely and run the underlying commands:

### 5.1 Health check

```bash
.venv/bin/python scripts/verify-setup.py
```

### 5.2 Dagster job

```bash
docker compose --env-file .env \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.openmetadata.yml \
  -f docker/docker-compose.superset.yml \
  exec dagster-webserver \
  dagster job execute \
  -f /app/dagster/definitions.py \
  -j demo_data_flow_job
```

### 5.3 Gold SQL assertion

```bash
.venv/bin/python scripts/verify-demo.py
```

All three exiting `0` is equivalent to `make demo` passing.

## 6. Manual confirmation in the browser

Once the command line passes, you can confirm visually.

### 6.1 SLH portal

Start the local operator/demo portal:

```bash
make health
```

Open:

```text
http://127.0.0.1:8090/health
```

Confirm that entity identity, core UI links, demo readiness, demo flow, and the service health table all match the running environment. Only continue once every service shows `PASS`.

### 6.2 Dagster

Open:

```text
http://localhost:3000
```

Confirm:

- the most recent run is named `demo_data_flow_job`
- the run status is success
- the Bronze, Silver, and Gold assets are all materialized in the asset graph
- `gold_features_min_rows_check` passed

### 6.3 MinIO

Open:

```text
http://localhost:9001
```

Default credentials come from `.env`:

```text
MINIO_ROOT_USER=sololakehouse
MINIO_ROOT_PASSWORD=sololakehouse123
```

Confirm the buckets:

- `sololakehouse`
- `sololakehouse-audit`
- `mlflow-artifacts`

All medallion layers are Iceberg tables under the warehouse prefix:

```text
sololakehouse/warehouse/bronze.db/ecb_rates/
sololakehouse/warehouse/bronze.db/dax_daily/
sololakehouse/warehouse/silver.db/ecb_rates_cleaned/
sololakehouse/warehouse/silver.db/dax_daily_cleaned/
sololakehouse/warehouse/gold.db/ecb_dax_features/
```

Each contains `data/` (Parquet data files) and `metadata/` (Iceberg manifests and snapshots).

### 6.4 Trino

Open:

```text
http://localhost:8080
```

The Trino UI is mainly for inspecting query execution. The actual SQL assertion is performed by `scripts/verify-demo.py`.

## 7. What each step proves

| Step | What it proves | Why it matters |
|---|---|---|
| `make verify` | All base services are available | Avoids guessing whether Trino, MinIO, or Dagster is at fault when a pipeline fails |
| `demo_data_flow_job` | Data flows from source into Bronze/Silver/Gold | Proves the platform does more than start containers — data actually moves |
| `gold_features` | The Gold Iceberg table is written and registered | Proves the query layer and table-format boundary both work |
| `gold_features_min_rows_check` | Gold is not an empty table | Prevents a "succeeded but produced no business data" false positive |
| `scripts/verify-demo.py` | Gold is queryable through Trino with a non-zero row count | Proves the consumption surface works |

## 8. Common failures and how to handle them

### 8.1 `make verify` fails

Identify the failing service first:

```bash
docker ps
docker logs --tail 200 slh-postgres
docker logs --tail 200 slh-hive-metastore
docker logs --tail 200 slh-trino
docker logs --tail 200 slh-dagster-webserver
```

If OpenMetadata or Superset has only just started, wait 2–5 minutes and retry:

```bash
make verify
```

### 8.2 Hive Metastore authentication failure

The symptom is usually:

```text
password authentication failed for user "postgres"
```

This normally comes from reusing an older `docker/data/postgres`. Try first:

```bash
make up
make verify
```

If it still fails and you can afford to delete local demo data:

```bash
make clean
make setup
```

### 8.3 Dagster job fails

Open:

```text
http://localhost:3000
```

Find the most recent `demo_data_flow_job` and inspect the first failed step.

Useful logs:

```bash
docker logs --tail 300 slh-dagster-webserver
docker logs --tail 300 slh-dagster-daemon
```

### 8.4 Gold SQL assertion fails

Confirm Trino is healthy:

```bash
make verify
```

Confirm the demo job succeeded:

```bash
make pipeline DAGSTER_JOB=demo_data_flow_job
```

Then re-run:

```bash
.venv/bin/python scripts/verify-demo.py
```

If it still fails, check the Trino logs:

```bash
docker logs --tail 300 slh-trino
```

## 9. Recording the result

A useful record format:

```text
Command: make demo
Result: PASS
Health: all services PASS
Dagster job: demo_data_flow_job RUN_SUCCESS
Iceberg Gold rows: <n>
Timestamp: <YYYY-MM-DD HH:MM>
Environment: <OS + Docker version + Python version>
```

A minimal pass statement:

```text
SoloLakehouse make demo PASS.
The stack health check passed, Dagster demo_data_flow_job completed successfully,
and the Iceberg Gold table returned a non-zero row count through Trino.
```
