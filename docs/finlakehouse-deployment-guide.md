# FinLakehouse Deployment Guide

Phase 2 of the entity-template preparation: deploy the first independent
FinLakehouse instance on a dedicated VPS using the v2.5.1 template + ADR-020
(all-layer Iceberg).

## Prerequisites

- Dedicated VPS: 4 vCPU, 8 GB RAM, 40 GB SSD minimum.
- Ubuntu 22.04 LTS or Debian 12.
- Docker Engine 24+ and Docker Compose V2.
- Git, Make, Python 3.13+.
- Ports 3000, 5000, 8080, 8088, 8090, 8585, 9000, 9001 reachable on the host
  (firewall-restricted to operator IPs is strongly recommended).

## Runtime root layout

```
/opt/finlakehouse/
  app/          ← git clone of SoloLakehouse lives here
  data/         ← bind-mounted runtime state (MinIO, Postgres, Dagster, OM)
  backup/       ← manual and scheduled backup archives
  logs/         ← operator and scheduled-job logs
  .env          ← entity-specific credentials and config (never commit)
```

Create the layout before cloning:

```bash
sudo mkdir -p /opt/finlakehouse/{app,data,backup,logs}
sudo chown -R $USER:$USER /opt/finlakehouse
```

## Step 1 — Clone and configure

```bash
cd /opt/finlakehouse
git clone https://github.com/Jiahong-Que-9527/SoloLakehouse.git app
cd app

# Copy the FLH env template and fill in every CHANGE_ME value
cp docs/finlakehouse-env-template.env /opt/finlakehouse/.env
nano /opt/finlakehouse/.env
```

Mandatory edits in `.env`:

- `MINIO_ROOT_PASSWORD` — strong unique password
- `POSTGRES_PASSWORD` — strong unique password
- `S3_SECRET_KEY` / `AWS_SECRET_ACCESS_KEY` — must match `MINIO_ROOT_PASSWORD`
- `SUPERSET_SECRET_KEY` — long random string
- `SUPERSET_ADMIN_PASSWORD` — strong unique password

## Step 2 — Bind-mount data directory

The Compose file expects `docker/data/` relative to the repo root. Create a
symlink so the VPS runtime state lands under the entity root instead:

```bash
mkdir -p /opt/finlakehouse/data
ln -sfn /opt/finlakehouse/data /opt/finlakehouse/app/docker/data
```

Verify the link: `ls -la /opt/finlakehouse/app/docker/data` should show the
target `/opt/finlakehouse/data`.

## Step 3 — Start the stack

```bash
cd /opt/finlakehouse/app
ENV_FILE=/opt/finlakehouse/.env make setup
```

`make setup` runs: Python venv creation, dependency install, `make up`
(which starts all Compose services and runs `make init-iceberg`).

## Step 4 — Verify

```bash
ENV_FILE=/opt/finlakehouse/.env make verify
ENV_FILE=/opt/finlakehouse/.env make health
```

All services should show PASS. Health portal opens at `http://<VPS-IP>:8090/health`.

## Step 5 — Run the demo acceptance path

```bash
ENV_FILE=/opt/finlakehouse/.env make demo
```

Pass criteria:
- `make demo` exits 0.
- Dagster `demo_data_flow_job` succeeds.
- Trino returns row count > 0 for `iceberg.gold.ecb_dax_features`.

## Step 6 — Run the full pipeline

```bash
ENV_FILE=/opt/finlakehouse/.env make pipeline
```

This executes `full_pipeline_job` including the MLflow experiment. Verify in
MLflow UI (`http://<VPS-IP>:5000`) that at least one `ecb_dax_impact` run
appears with metrics.

## Step 7 — Record the restore drill

Before considering the entity live, run a disposable restore drill against this
deployment. See `docs/entity-backup-restore-runbook.md` and create a record
under `docs/restore-drills/YYYY-MM-DD-finlakehouse-iceberg-restore-drill.md`.

The previous drill (`docs/restore-drills/2026-05-17-entity-template-restore-drill.md`)
was performed against the Parquet-era baseline and does **not** cover the
Iceberg write path. A new drill is required before 24/7 operation begins.

## Ongoing operations

### Backup cadence (minimum)

- Daily: `mc mirror` all three buckets (`finlakehouse-data`, `finlakehouse-audit`,
  `finlakehouse-mlflow`) to offsite storage.
- Daily: `pg_dump` of `hive_metastore`, `mlflow`, `dagster_storage`, and
  `superset_metadata` databases.
- Per-release: snapshot the `/opt/finlakehouse/.env` and record the release tag.

### Health check

Run `make health` (or open the portal at port 8090) daily. All services should
show PASS before kicking off a pipeline run.

### Scheduled pipeline

The Dagster scheduler handles `full_pipeline_job`. Confirm the schedule is
enabled in Dagster UI and the first scheduled run completes before declaring
the entity operational.

## Entity isolation rules

- Never share the `/opt/finlakehouse/data/` bind mount with the SoloLakehouse
  reference runtime or any other entity.
- Never run `make clean` on the VPS runtime — it deletes `docker/data/`.
  Use `make down` to stop services while preserving state.
- Side-by-side upgrades: clone the new version to a separate path
  (`/opt/finlakehouse/app-v2.6/`) before switching the symlink.
