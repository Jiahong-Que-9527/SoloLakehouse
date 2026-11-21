# Governed Energy Data Product

<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

**G04 · First governed release live (2026-11-21)** · [Google Cloud roadmap](../README.md) · [Design](docs/design.md) · [Implementation plan](docs/implementation.md) · [Cloud verification](docs/cloud-verification.md)

Publish an approved energy dataset with a versioned schema, documented quality rules, restricted access and auditable release records.

**Status:** first delivery recorded. The contracts are versioned YAML;
the offline gate checks key-set completeness, grain uniqueness, value
range and freshness; and the release boundary (approval, immutable
candidate IDs, checksum retry adoption, quarantine on failure,
append-only withdrawal) is tested against a store port (37 tests). The
first publication is live: the gate passed all five checks, the
authorised view serves the immutable version table
`cand-2026-11-21-fourth` (672 rows) to the analyst identity only, and
the release/withdrawal drill ran as the producer identity. The full
evidence — five publication defects found and fixed on the way, the
identity/denial matrix and the drill — is recorded in
`docs/cloud-verification.md`.

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
