# Governed Energy Data Product

<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

**G04 · Planned** · [Google Cloud roadmap](../README.md) · [Design](docs/design.md) · [Implementation plan](docs/implementation.md)

Publish an approved energy dataset with a versioned schema, documented quality rules, restricted access and auditable release records.

## Technical scope

BigQuery, IAM, data quality checks, catalog and lineage.

## Input and output

- **Input.** A versioned [G01](../01-european-energy-pipeline/README.md) release or a seeded fixture with the same schema, including one invalid input.
- **Output.** An approved BigQuery view, a quality report, a release record and evidence of access control and lineage.

## Acceptance

1. Block publication when a required field or quality rule fails. Retain the failed check and keep the preceding release queryable.
2. Show a reader accessing the approved view and being denied raw data access. Capture the tested identities and results.
3. Trace a published query result to its release, input and code revision. Record verifiable catalog, lineage and audit evidence from the test environment.

<!-- [房玄龄·2026-11-17] Document implementation order and acceptance evidence. -->
