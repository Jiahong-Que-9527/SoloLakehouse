# Google Cloud project roadmap

<!-- [房玄龄·2026-11-15] Record the platform projects, milestones and acceptance criteria. -->
<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

Build cloud infrastructure and batch delivery first. Add API access, event handling, governance and MLOps, then reuse proven deployment steps. The energy metric
provides a common workload for G01 to G05. Each numbered directory owns its delivery. `docs/design.md` is the design. The README is the short brief. G01 has an implemented local pipeline, scoped CI and a verified 2025 snapshot. GCP deployment is planned. G02 through G06 have designs and phased implementation plans.

## Projects in learning order

1. **G01** · [European Energy Pipeline](01-european-energy-pipeline/README.md)
   Deploy a scheduled batch job and publish a repeatable electricity-load table.
   [Design](01-european-energy-pipeline/docs/design.md)
2. **G02** · [Energy Analytics API](02-energy-analytics-api/README.md)
   Serve approved indicators through an authenticated, measured REST API.
   [Design](02-energy-analytics-api/docs/design.md)
3. **G03** · [Aviation Event Processing](03-aviation-event-processing/README.md)
   Test duplicate and late events, retries, dead-letter handling and replay.
   [Design](03-aviation-event-processing/docs/design.md)
4. **G04** · [Governed Energy Data Product](04-governed-energy-data-product/README.md)
   Release a quality-checked data product with access and provenance evidence.
   [Design](04-governed-energy-data-product/docs/design.md)
5. **G05** · [Energy Forecasting MLOps](05-energy-forecasting-mlops/README.md)
   Train, register, batch-score and roll back a versioned model.
   [Design](05-energy-forecasting-mlops/docs/design.md)
6. **G06** · [Cloud Platform Factory](06-cloud-platform-factory/README.md)
   Provision isolated environments and demonstrate repeatable deployment, cost tracking and retirement.
   [Design](06-cloud-platform-factory/docs/design.md)

## Project handoffs and independent delivery

G01 publishes a versioned metric schema and a data release. G02 consumes a
read-only view. G03 reuses the schema in a synthetic event fixture and has
its own output table. G04 can validate a release from G01. G05 can train on
a fixed G04 release. G06 reuses deployment steps from working projects.

Each consumer can use a small compatible fixture to validate or deploy in
its own environment. Integration uses explicit release IDs or a pinned
model version. A fork includes the whole repository and can select one
project's checks and deployment. Cloud deployment requires the operator's
own environment and permissions.

The separate [aviation serving integration](../Fraport-adsb-intelligence/06-model-serving/README.md)
can apply G05 delivery practices to the flagship model.

## Delivery priorities

Build G01 first. G04 and G06 are the other platform engineering priorities.
G02 and G03 cover consumption and operational reliability. G05 adds the
model lifecycle. Start from a small baseline and record observed cloud cost.

OpenSky Data Ingestion is the first public SoloLakehouse delivery. G01
starts the GCP-specific route.

<!-- [房玄龄·2026-11-17] Document implementation order and acceptance evidence. -->
