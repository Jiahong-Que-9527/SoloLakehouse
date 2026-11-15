# 04 · Aviation Lakehouse Integration

**Runtime:** Databricks, reading Gold releases from Cloud Storage.

Connect this programme's Gold releases into Databricks, following the
[Databricks roadmap](../../databricks/README.md). This subproject owns the
data contract and the integration with Cloud Storage.

## Scope

- Define how Databricks reads the Gold releases from Cloud Storage
  (external locations, credentials, governance). Bronze and Silver stay
  local and are not available here.
- Map the project 02 Gold schemas to the Aviation Lakehouse Bronze, Silver and
  Gold tables. The release is the input, so its Delta tables start from the
  published Gold data.
- Verify event identity, proxy label coverage and the feature cutoff on a
  small batch, then on a larger slice.
- Document governance: ownership, access and retention.

## Milestones

- **M1.** Schema mapping document and a synthetic release read from Cloud
  Storage.
- **M2.** One month through Bronze, Silver and Gold with checks.
- **M3.** Feature table contract agreed with project 05.

## Acceptance

- The same input and code revision gives the same Gold output.
- Proxy label coverage is reported with each run.
- Features use only data available before the prediction cutoff.

## Depends on

Project 02 Gold releases and the Landing bucket from project 03. Coordinate with the Databricks Aviation Lakehouse project.

## Outputs

Data contract, Gold feature table and a coverage report.
