# Unity Catalog Governance

<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

**D04 · Accepted on Free Edition** · [Databricks roadmap](../README.md) · [Playbook](../docs/free-edition-cli-playbook.md) · [Design](docs/design.md) · [Implementation](docs/implementation.md) · [Runbook](docs/free-edition-run.md) · [Workspace evidence](evidence/free-edition-acceptance.json)

Define and test data access, quality and provenance for producer, analyst and ML roles in a shared financial lakehouse.

## Technical scope

Unity Catalog, permissions, lineage, quality checks and workspace audit evidence.

## Input and output

- **Input.** An approved [D01](../01-ecb-delta-lakehouse/README.md) Gold release or an equivalent fixture seeded into the project catalog and schema.
- **Output.** A catalog and permission model, tested quality and access rules, and evidence linking a consumed table version to its source and job.

## Acceptance

1. Verify the producer can publish, the analyst can read the approved dataset, and a consumer is denied access outside its scope.
2. Apply a failed quality check to an invalid fixture and capture evidence that the release was blocked.
3. Verify lineage and access-audit records using the available workspace features. Record which checks were exercised in the workspace.

## Free Edition execution scope

- **Verified on Free Edition:** a CLI-deployed serverless job created isolated dev and prod schemas in `workspace`, queried the three controlled views, rejected duplicate-key candidates before moving the release pointer, and then published a corrected release. The release links matching observations in Bronze Delta version 3 and Gold Delta version 2 to the job run.
- **Governance evidence:** Unity Catalog recorded the Bronze → Silver → Gold edges. The job temporarily granted and revoked an explicit `SELECT` for the view owner and recorded the revoke in `grant_change`. The owner's continued read was confirmed after the grant was removed. A separate system audit query returned zero matching events for the view during the job window.
- **Warehouse verified:** the 2X-Small serverless SQL Warehouse returned the approved `forecast_feature` projection for release `corrected` through the Statement Execution API. The statement ID and result are in the workspace evidence.
- **Deferred on Free Edition:** live five-role allow/deny checks, identity-dependent column masking and account-level audit delivery.

### D05 handoff

The approved feature projection is `release_id`, `series_key`, `observation_date` and `fx_rate`. Filter the evidence's `forecast_feature` view to release `corrected` for a deployment smoke test. The evidence also pins Gold Delta version 2 and its source batch. The single synthetic observation is sized for governance verification.

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->
