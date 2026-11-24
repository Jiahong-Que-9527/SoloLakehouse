# Unity Catalog Governance implementation plan

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->

**Status:** Free Edition governance and 2X-Small SQL Warehouse verification passed. [Brief](../README.md) · [Design](design.md) · [Runbook](free-edition-run.md) · [Observed evidence](../evidence/free-edition-acceptance.json)

## First delivery

Deliver a governed release with a reproducible permission review. Seed a D01-shaped fixture with synthetic restricted fields. Record available workspace identities, catalog privileges and audit/lineage visibility.

## Implementation sequence

1. Write an allow/deny matrix before granting access. Cover producer, analyst, risk analyst, ML reader and auditor. Assign separate test schemas and runtime identities, including the intended dev-to-prod write denial.

2. Publish a small approved release and controlled consumer views. Query as each actual test principal. Pair a permitted read with the expected denied raw read, restricted-column access or write as appropriate. Record the effective principal and query ID.

3. Submit a candidate with a duplicate key or null measure. Confirm the visible release and query results remain unchanged. Publish a corrected candidate under a fresh release ID and trace one row to its source batch and Delta version.

4. Exercise one permission change, recheck access as the affected principal and verify other roles retain their expected access. Distinguish inherited privileges from grants under test. Restore the exercise grant state.

5. Capture workspace lineage and audit evidence where available. For unavailable features record the missing privilege or capability and the check still outstanding. Hand D05 a pinned release reference and an approved feature projection.

## Portfolio evidence

Evidence: a compact role matrix with observed outcomes, a release trace, and one grant-change record. These demonstrate governance beyond an administrative screenshot. Link measured results from the brief after execution.
