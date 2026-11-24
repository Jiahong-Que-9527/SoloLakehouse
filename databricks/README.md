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
| **D02** · ETL Automation | Planned | Full (4 sequential tasks ≤ 5 limit) | `databricks bundle` + GitHub Actions `bundle validate` | Keep schedules paused |
| **D03** · CDC Lakehouse | Planned | Full (managed UC Volume) | `databricks fs cp` + `bundle run` (`availableNow` or batch fallback) | External cloud bucket |
| **D04** · UC Governance | Planned | Partial subset | CLI + `sql/statements` API on 2X-Small warehouse | 5-role denials, masking, audit tables |
| **D05** · Forecasting MLOps | Planned | Full (CPU Serverless + MLflow) | Parameterized `bundle run` for scoring & rollback | Enterprise multi-env registry |
| **D06** · Platform Factory | **Deferred** | Not supported | — | Terraform account API + 2 Service Principals |

## Projects in learning order

1. **D01** · [ECB Delta Lakehouse](01-ecb-delta-lakehouse/README.md) — **Accepted on Free Edition** (Delta MERGE, Time Travel and replay verified)
   Model ECB rates with Delta and verify versioned Bronze, Silver and Gold outputs.
   [Design](01-ecb-delta-lakehouse/docs/design.md) · [Implementation plan](01-ecb-delta-lakehouse/docs/implementation.md)
2. **D02** · [Financial ETL Automation](02-financial-etl-automation/README.md)
   Deploy scheduled tasks and verify retries, recovery and publication.
   [Design](02-financial-etl-automation/docs/design.md) · [Implementation plan](02-financial-etl-automation/docs/implementation.md)
3. **D03** · [Financial CDC Lakehouse](03-financial-cdc-lakehouse/README.md)
   Apply incremental updates and withdrawals and reconcile after a checkpoint restart.
   [Design](03-financial-cdc-lakehouse/docs/design.md) · [Implementation plan](03-financial-cdc-lakehouse/docs/implementation.md)
4. **D04** · [Unity Catalog Governance](04-unity-catalog-governance/README.md)
   Verify permissions, lineage and the evidence behind a governed data release.
   [Design](04-unity-catalog-governance/docs/design.md) · [Implementation plan](04-unity-catalog-governance/docs/implementation.md)
5. **D05** · [Financial Forecasting MLOps](05-financial-forecasting-mlops/README.md)
   Track time-series training, register a model and validate batch predictions.
   [Design](05-financial-forecasting-mlops/docs/design.md) · [Implementation plan](05-financial-forecasting-mlops/docs/implementation.md)
6. **D06** · [Lakehouse Platform Factory](06-lakehouse-platform-factory/README.md) — **Deferred on Free Edition** (multi-principal workspace required)
   Provision a repeatable catalog, permissions and job environment for another team.
   [Design](06-lakehouse-platform-factory/docs/design.md) · [Implementation plan](06-lakehouse-platform-factory/docs/implementation.md)

## Project handoffs and independent delivery

The planned D01 release will identify a versioned financial data product. D02 can package its
transformations, D03 can reuse its key conventions in correction fixtures,
and D04 can apply governance to its Gold schema. D05 selects a pinned Gold
snapshot. D06 combines delivery and governance patterns exercised by the
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

Start with D01, then demonstrate scheduled delivery and failure recovery
in D02. D03 and D04's Free Edition governance subset are the next data platform
demonstrations, followed by D05 model delivery. D06 (and D04's multi-principal
enterprise checks) remain deferred until a multi-principal workspace with
Account Console / Terraform permissions is approved. Always record the scope of
actual workspace evidence and any `not_available` checks.

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->
