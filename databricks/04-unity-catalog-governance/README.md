# Unity Catalog Governance

<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

**D04 · Planned** · [Databricks roadmap](../README.md) · [Design](docs/design.md)

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
