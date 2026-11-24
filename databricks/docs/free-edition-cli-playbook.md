# Databricks Free Edition & CLI Playbook

This track (`databricks/01..06`) runs on **Databricks Free Edition** (**€0**, Serverless compute) so it requires **no GCP billing upgrade** (respecting the repository [GCP cost gate](../../AGENTS.md)) and **no local Java/PySpark installation** for unit tests and CI.

## 1. Platform constraints on Free Edition

- **Serverless-only compute:** classic clusters, custom VM node types, and instance pools are unavailable.
- **SQL Warehouse cap:** one **2X-Small** Serverless SQL Warehouse per account.
- **Job concurrency & Fair Usage:** maximum **5 concurrent job tasks** per account under daily and monthly serverless usage quotas. Exceeding the daily quota pauses serverless compute until reset while keeping tables and workspace files intact.
- **Single-user workspace:** no Account Console, no Service Principals or M2M OAuth, no account/workspace-level Terraform provisioning, and no external GCS/S3/ADLS storage credentials. Use managed Unity Catalog Volumes (`/Volumes/workspace/<schema>/<volume>`) instead of external buckets.
- **Outbound network:** restricted to an allowlist; ship small fixtures inside the Declarative Automation Bundle or upload them to a managed UC Volume.

## 2. Using the Databricks CLI on Free Edition (PAT, not OAuth)

The **Databricks CLI** works well with Free Edition for bundles, jobs, files, catalog inspection, and SQL execution — **provided you authenticate with a Personal Access Token (PAT)**.

> **Important:** Do **not** run `databricks auth login` against a Free Edition host. Free Edition workspaces do not expose the enterprise OAuth U2M endpoints (`databricks OAuth is not supported for this host`).

### Install and configure

```bash
# Install Databricks CLI in WSL2 / Linux
curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh
databricks --version
```

Generate a PAT in the Free Edition UI (**Settings → Developer → Access tokens → Generate new token**), then configure a named CLI profile (`slh-free`) without committing credentials to Git:

```bash
databricks configure --profile slh-free
# Host:  https://<your-free-edition-workspace-url>
# Token: <your-pat>
```

Or in `~/.databrickscfg` (`chmod 600 ~/.databrickscfg`):

```ini
[slh-free]
host  = https://<your-free-edition-workspace-url>
token = <your-pat>
```

For GitHub Actions, store `DATABRICKS_HOST` and `DATABRICKS_TOKEN` as repository/environment secrets instead of `~/.databrickscfg`.

### Connectivity smoke check

```bash
databricks current-user me --profile slh-free
databricks schemas list workspace --profile slh-free
databricks warehouses list --profile slh-free
```

## 3. CLI capability boundary on Free Edition

| Area | Supported via CLI on Free Edition | Not supported / deferred |
|---|---|---|
| **Bundles (DABs)** | `databricks bundle validate`, `deploy`, `run`, `destroy` targeting Serverless `notebook_task` / `spark_python_task` | Classic cluster configs, instance pools |
| **Jobs & evidence** | `databricks jobs run-now`, `get-run`, `get-run-output`, `list-runs` (capture JSON returned by `dbutils.notebook.exit`) | > 5 concurrent tasks |
| **Storage & workspace** | `databricks fs cp` to managed UC Volumes (`dbfs:/Volumes/workspace/...`), `databricks workspace` | External GCS/S3 storage credentials (`storage-credentials`) |
| **Catalog & SQL** | `databricks schemas/tables/volumes`, `databricks api post /api/2.0/sql/statements` on the 2X-Small warehouse | Account-level metastore creation, multi-principal grants, column masking, audit system tables |
| **Terraform** | Not used for Free Edition infrastructure | Account/workspace provisioning and Service Principal isolation |

## 4. D01–D06 CLI execution plan

1. **D01 · ECB Delta Lakehouse** — Deploy via `databricks bundle deploy -t dev --profile slh-free`, run `databricks bundle run d01_ecb_lakehouse -t dev --profile slh-free`, and capture `dbutils.notebook.exit` JSON via `databricks jobs get-run-output` (plus optional SQL Statement API `VERSION AS OF` checks).
2. **D02 · Financial ETL Automation** — Package `ingest -> transform -> quality -> publish` as 4 sequential tasks (under the 5-task cap) in `databricks.yml`. GitHub Actions runs `pytest` + `databricks bundle validate`; CLI triggers the valid run, quality-stop failure run, and repair replay. Keep schedules paused after verification.
3. **D03 · Financial CDC Lakehouse** — Upload seeded CDC event files via bundle sync or `databricks fs cp` into a managed UC Volume (`/Volumes/workspace/<schema>/cdc_events`). Run `availableNow=True` Structured Streaming `MERGE`, or the explicitly labeled batch-MERGE checkpoint fallback if streaming triggers Free Edition restrictions.
4. **D04 · Unity Catalog Governance (Free Edition subset)** — Use the CLI-deployed serverless job for isolated schemas, controlled views, the release-pointer gate and the `grant_change` ledger. Use the Unity Catalog API for the table lineage graph and a separate `sql:read:restricted-query` profile for the 2X-Small Warehouse Statement API read. See the [D04 runbook](../04-unity-catalog-governance/docs/free-edition-run.md) and [workspace evidence](../04-unity-catalog-governance/evidence/free-edition-acceptance.json).
5. **D05 · Financial Forecasting MLOps** — Run CPU Serverless jobs on a pinned Delta snapshot, log last-value, linear, and candidate runs to MLflow, and register eligible versions. Use parameterized `databricks bundle run` batches for scoring, replay, rollback, and residual monitoring. See the [D05 runbook](../05-financial-forecasting-mlops/docs/free-edition-run.md) and [workspace evidence](../05-financial-forecasting-mlops/evidence/free-edition-acceptance.json).
6. **D06 · Lakehouse Platform Factory** — Validate the two stack templates with mocked Terraform plans and strict Bundle checks in CI. The reference job also passed a single-identity workspace run. Dual-stack deployment under separate service principals, cross-identity isolation and retirement are skipped in Free Edition and excluded from completion. See the [D06 runbook](../06-lakehouse-platform-factory/docs/runbook.md).
