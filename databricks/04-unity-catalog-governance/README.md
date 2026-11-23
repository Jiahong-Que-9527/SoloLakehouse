# Unity Catalog Governance

<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

**D04 · Planned (Databricks Free Edition subset · multi-principal checks deferred)** · [Databricks roadmap](../README.md) · [Playbook](../docs/free-edition-cli-playbook.md) · [Design](docs/design.md) · [Implementation plan](docs/implementation.md)

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

- **In scope on Free Edition (CLI + 2X-Small SQL Warehouse):** dedicated schemas inside `workspace`, controlled consumer views (`fx_indicator_current`, `transaction_risk_detail`, `forecast_feature`), quality-gated `current_release` pointer, `grant_change` evidence ledger, and SQL verification via `databricks api post /api/2.0/sql/statements`.
- **Deferred / `not_available` on Free Edition:** 5-role multi-principal live permission denials (no Service Principals / M2M OAuth), column masking policies, and account-level audit system tables — recorded explicitly as `not_available` until a multi-principal workspace is approved. See [Free Edition & CLI Playbook](../docs/free-edition-cli-playbook.md).

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->
