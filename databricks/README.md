# Databricks project roadmap

<!-- [房玄龄·2026-11-15] Record the platform projects, milestones and acceptance criteria. -->
<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

Start with Spark and Delta Lake, then progress through job deployment, incremental state, Unity Catalog, MLflow and reusable lakehouse environments. Financial
data and versioned releases connect the projects. Each numbered directory is a standalone project. `docs/design.md` is the design and the README is the short brief. **D01** passed Databricks Free Edition verification. The roadmap below records the remaining stages.

## Execution environment: Databricks Free Edition (2026-11-23)

Owner decision: run the Databricks track on **Databricks Free Edition** (€0, Serverless compute; no GCP billing upgrade; local CI runs pure-Python contract and transformation tests with `uv`/`pytest` and requires no local Java or PySpark). See the [Free Edition & CLI Playbook](docs/free-edition-cli-playbook.md) for PAT authentication (`databricks configure` — not OAuth `databricks auth login`), Fair Usage quotas, and the D01–D06 CLI plan.

| Project | Status | Free Edition support | CLI delivery path | Deferred items |
|---|---|---|---|---|
| **D01** · ECB Delta | **Accepted** | Full | `databricks bundle deploy/run` + `jobs get-run-output` | — |
| **D02** · ETL Automation | **Accepted** | Full (4 sequential tasks ≤ 5 limit) | `databricks bundle` + GitHub Actions `bundle validate` | Keep schedules paused |
| **D03** · CDC Lakehouse | **Accepted** | Full (managed UC Volume) | `bundle run` with Auto Loader and `availableNow`, plus independent batch replay | External cloud bucket |
| **D04** · UC Governance | **Accepted on Free Edition** | Partial subset | CLI serverless job, Unity Catalog lineage API, and 2X-Small SQL Warehouse Statement API | 5-role denials, masking, account-level audit delivery |
| **D05** · Forecasting MLOps | **Accepted** | CPU Serverless, MLflow and Unity Catalog Model Registry verified | Parameterized `bundle run` for scoring, replay, rollback and monitoring | Enterprise multi-env registry |
| **D06** · Platform Factory | **Template and CI validated** · live acceptance deferred | Mocked Terraform plans and strict Bundle validation | Two stack configurations and an operator runbook | Live deployment, two service principals and retirement drill |

## Projects in learning order

1. **D01** · [ECB Delta Lakehouse](01-ecb-delta-lakehouse/README.md) — **Accepted on Free Edition** (Delta MERGE, Time Travel and replay verified)
   Model ECB rates with Delta and verify versioned Bronze, Silver and Gold outputs.
   [Design](01-ecb-delta-lakehouse/docs/design.md) · [Implementation plan](01-ecb-delta-lakehouse/docs/implementation.md)
2. **D02** · [Financial ETL Automation](02-financial-etl-automation/README.md) — **Accepted** (GitHub Actions deploy, scheduled run, quality gate, retry and bounded replay)
   Deploy scheduled tasks and verify retries, recovery and publication.
   [Design](02-financial-etl-automation/docs/design.md) · [Implementation plan](02-financial-etl-automation/docs/implementation.md)
3. **D03** · [Financial CDC Lakehouse](03-financial-cdc-lakehouse/README.md) — **Accepted** (streaming restart, delete and replay verified)
   Apply incremental updates and withdrawals and reconcile after a checkpoint restart.
   [Design](03-financial-cdc-lakehouse/docs/design.md) · [Implementation plan](03-financial-cdc-lakehouse/docs/implementation.md)
4. **D04** · [Unity Catalog Governance](04-unity-catalog-governance/README.md) — controlled views, quality gate, lineage and grant ledger verified
   Verify permissions, lineage and the evidence behind a governed data release.
   [Design](04-unity-catalog-governance/docs/design.md) · [Implementation plan](04-unity-catalog-governance/docs/implementation.md)
5. **D05** · [Financial Forecasting MLOps](05-financial-forecasting-mlops/README.md) — **Accepted** (chronological evaluation, registration, batch replay and rollback verified)
   Track time-series training, register a model and validate batch predictions.
   [Design](05-financial-forecasting-mlops/docs/design.md) · [Implementation plan](05-financial-forecasting-mlops/docs/implementation.md)
6. **D06** · [Lakehouse Platform Factory](06-lakehouse-platform-factory/README.md) — **Template and CI validated** (live acceptance requires a multi-principal workspace)
   Provision a repeatable catalog, permissions and job environment for another team.
   [Design](06-lakehouse-platform-factory/docs/design.md) · [Implementation plan](06-lakehouse-platform-factory/docs/implementation.md)

## Project handoffs and independent delivery

The verified D01 release identifies a versioned financial data product. D02 packages its
transformations. D03 reuses its key convention in the correction fixture,
and D04 provides a governed fixture with a pinned Gold version and an approved
feature projection for a D05 smoke test. D06 combines delivery and governance patterns exercised by the
earlier projects.

Each project can validate against a local or workspace fixture with its
own deploy target. Pin a source, table or model version for integration.
Fork the repository as a unit and run only the selected project's checks
or deployment. Record which capabilities were actually validated in the
workspace, including job execution, streaming, lineage and audit access.

The [local ECB project](../local/ecb-silver-pipeline/README.md) provides a
policy-rate quality reference. The Databricks track uses the finance
workloads described above.

## Delivery priorities

D01–D05 have workspace acceptance evidence. D06 template validation runs in CI.
D06 live acceptance and D04's multi-principal checks require an approved workspace
with Account Console and Terraform permissions. Always record the scope of
actual workspace evidence and any `not_available` checks.

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->
