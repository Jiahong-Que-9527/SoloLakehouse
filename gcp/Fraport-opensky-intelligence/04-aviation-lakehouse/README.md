# 04 · Aviation Lakehouse Integration

**Runtime:** Databricks, reading and writing Cloud Storage.

Connect this programme's Bronze and Silver data to the Databricks
[Aviation Lakehouse](../../../databricks/aviation-lakehouse/README.md)
project. That project owns the Delta transformation code. This subproject owns
the data contract and the integration with GCS.

## Scope

- Define how Databricks reads the Bronze and Silver datasets from GCS
  (external locations, credentials, governance).
- Map project 01 and 02 schemas to the Aviation Lakehouse Bronze, Silver and
  Gold tables.
- Verify event identity, proxy label coverage and the feature cutoff on a
  small batch, then on a larger slice.
- Document governance: ownership, access and retention.

## Milestones

- **M1.** Schema mapping document and a fixture batch read from GCS.
- **M2.** One month through Bronze, Silver and Gold with checks.
- **M3.** Feature table contract agreed with project 05.

## Acceptance

- The same input and code revision gives the same Gold output.
- Proxy label coverage is reported with each run.
- Features use only data available before the prediction cutoff.

## Depends on

Projects 01 and 02. Coordinate with the Databricks Aviation Lakehouse project.

## Outputs

Data contract, Gold feature table and a coverage report.
