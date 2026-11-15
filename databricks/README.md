# Databricks project roadmap

<!-- [房玄龄·2026-11-15] Record the platform projects, milestones and acceptance criteria. -->
<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

Start with Spark and Delta Lake, then progress through job deployment, incremental state, Unity Catalog, MLflow and reusable lakehouse environments. Financial
data and versioned releases connect the projects. Each numbered directory is a standalone planned project. `docs/design.md` is the design. The README is the short brief. These directories do not contain application code yet.

## Projects in learning order

1. **D01** · [ECB Delta Lakehouse](01-ecb-delta-lakehouse/README.md)
   Model ECB rates with Delta and verify versioned Bronze, Silver and Gold outputs.
   [Design](01-ecb-delta-lakehouse/docs/design.md)
2. **D02** · [Financial ETL Automation](02-financial-etl-automation/README.md)
   Deploy scheduled tasks and verify retries, recovery and publication.
   [Design](02-financial-etl-automation/docs/design.md)
3. **D03** · [Financial CDC Lakehouse](03-financial-cdc-lakehouse/README.md)
   Apply incremental updates and withdrawals and reconcile after a checkpoint restart.
   [Design](03-financial-cdc-lakehouse/docs/design.md)
4. **D04** · [Unity Catalog Governance](04-unity-catalog-governance/README.md)
   Verify permissions, lineage and the evidence behind a governed data release.
   [Design](04-unity-catalog-governance/docs/design.md)
5. **D05** · [Financial Forecasting MLOps](05-financial-forecasting-mlops/README.md)
   Track time-series training, register a model and validate batch predictions.
   [Design](05-financial-forecasting-mlops/docs/design.md)
6. **D06** · [Lakehouse Platform Factory](06-lakehouse-platform-factory/README.md)
   Provision a repeatable catalog, permissions and job environment for another team.
   [Design](06-lakehouse-platform-factory/docs/design.md)

## Project handoffs and independent delivery

D01 publishes a versioned financial data product. D02 can package its
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
policy-rate quality reference. The [aviation Lakehouse integration](../Fraport-adsb-intelligence/04-aviation-lakehouse/README.md)
can apply the deployment and governance practices to a separate aviation
release.

## Delivery priorities

Start with D01, then demonstrate scheduled delivery and failure recovery
in D02. D03 and D04 are the priority demonstrations for a data platform
role. D05 adds model delivery after the data path is proven. D06 follows
verified deployment and governance. Use a workspace with the permissions
needed for each milestone and record the scope of actual cloud evidence.
