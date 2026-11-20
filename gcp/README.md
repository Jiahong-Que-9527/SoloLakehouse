# Google Cloud project roadmap

<!-- [房玄龄·2026-11-15] Record the platform projects, milestones and acceptance criteria. -->
<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->
<!-- [李淳风·2026-11-20] Link the G01 implementation plan. -->

This series explores how to deliver, govern and operate data products on Google Cloud. German electricity load provides the main dataset. The event-processing project also uses synthetic airport events.

**Cost gate (all agents):** the billing account is on a Free Trial that
expires 2027-02-11. Any operation that may cost beyond the trial credits
requires the owner's explicit approval before execution — see the
[GCP cost gate](../AGENTS.md).

**Implemented locally:** G01 downloads SMARD data, normalizes quarter-hour energy to UTC and audits replay. The 2025 snapshot contains 35,040 continuous intervals. Two annual exports produced the same checksum. [Annual acceptance](01-european-energy-pipeline/docs/year-2025-verification.md) · [Project CI](../.github/workflows/energy-pipeline.yml)

**Planned cloud delivery:** G01's first cloud milestone is a Cloud Run Job with Cloud Storage and BigQuery. G02–G06 have design and implementation guides. The numbered list gives a learning order. Each project can exercise its own bounded fixture.

## Projects in learning order

1. **G01** · [European Energy Pipeline](01-european-energy-pipeline/README.md)
   Deploy a scheduled batch job and publish a repeatable electricity-load table.
   [Design](01-european-energy-pipeline/docs/design.md) · [Implementation plan](01-european-energy-pipeline/docs/implementation.md)
2. **G02** · [Energy Analytics API](02-energy-analytics-api/README.md)
   Serve approved indicators through an authenticated, measured REST API.
   [Design](02-energy-analytics-api/docs/design.md) · [Implementation plan](02-energy-analytics-api/docs/implementation.md)
3. **G03** · [Aviation Event Processing](03-aviation-event-processing/README.md)
   Test duplicate and late events, retries, dead-letter handling and replay.
   [Design](03-aviation-event-processing/docs/design.md) · [Implementation plan](03-aviation-event-processing/docs/implementation.md)
4. **G04** · [Governed Energy Data Product](04-governed-energy-data-product/README.md)
   Release a quality-checked data product with access and provenance evidence.
   [Design](04-governed-energy-data-product/docs/design.md) · [Implementation plan](04-governed-energy-data-product/docs/implementation.md)
5. **G05** · [Energy Forecasting MLOps](05-energy-forecasting-mlops/README.md)
   Train, register, batch-score and roll back a versioned model.
   [Design](05-energy-forecasting-mlops/docs/design.md) · [Implementation plan](05-energy-forecasting-mlops/docs/implementation.md)
6. **G06** · [Cloud Platform Factory](06-cloud-platform-factory/README.md)
   Provision isolated environments and demonstrate repeatable deployment, cost tracking and retirement.
   [Design](06-cloud-platform-factory/docs/design.md) · [Implementation plan](06-cloud-platform-factory/docs/implementation.md)

## Project handoffs and independent delivery

- **Data product and forecasting (G01 → G04 → G05).** G01 currently produces local Parquet and manifests. Its planned cloud publication adds a source release ID and ingestion timestamp. G04 will validate that input, preserve its identity in a separately versioned product release, and expose the approved data. G05 will pin the product release for training and derive average MW from interval energy in MWh and interval duration.
- **API access (G02).** G02 can start with its own seeded read-only view and test identities. In an integrated deployment, callers need permission to invoke the API and its runtime identity needs permission to query G04's approved view. Verify those permissions separately.
- **Event processing (G03).** Seeded energy revisions and synthetic airport events exercise duplicate delivery, retries and replay against independently expected results. G03 owns its output table and can run alongside the batch projects.
- **Environment provisioning (G06).** The factory will reuse verified deployment patterns and exercise its batch template with a one-row reference workload. Its acceptance evidence covers two isolated environments, scoped identities and retirement.

The separate [aviation serving integration](../Fraport-adsb-intelligence/06-model-serving/README.md)
can apply G05 delivery practices to the flagship model.

## Delivery priorities

Start with one G01 cloud run over a window already verified locally. Record the source revision, execution ID, output comparison, repeat-run behavior and observed cost. G04 can then demonstrate publication and withdrawal against a real release. G02 and G03 can proceed independently with fixtures. G06 becomes more useful after the first workloads have produced deployment evidence.

<!-- [房玄龄·2026-11-17] Document implementation order and acceptance evidence. -->

<!-- [房玄龄·2026-11-17] Clarify local evidence and planned project handoffs. -->
