# ADR-004: Gold table format and catalog

**Status:** Proposed. Blocked on a verification spike.

## Context

Gold releases (ADR-003) land in Cloud Storage. They need to become managed
tables that BigQuery, Databricks and Vertex AI can query, with snapshots that
link back to a release ID.

The candidates are:

- **Apache Iceberg on GCS** with a Google-managed catalog. It gives snapshots,
  schema evolution and an open format.
- **BigQuery native tables** loaded from the release Parquet. Simplest, but
  the data is held in BigQuery storage.
- **Delta Lake** in Databricks. The Aviation Lakehouse project already uses it
  (subproject 04).

The Google catalog service, its names, its regional availability, its engine
support for writes and the BigQuery integration have not been verified for
this programme.

## Decision

Prefer Apache Iceberg for the cloud Gold tables, provided a one-day spike on
synthetic data confirms every check below. Otherwise load BigQuery native
tables. Subproject 04 keeps Delta either way, because it is the integration
with the existing Databricks project.

## Spike checks

1. The Google catalog service is available in `europe-west3`, or in a region
   the programme accepts for the bucket and BigQuery location.
2. BigQuery can query the Iceberg tables, and the bucket and dataset
   locations are compatible.
3. At least one cheap writer works with the catalog: a Cloud Run Job using
   PyIceberg, or Spark on Dataproc Serverless. Record which one.
4. A release can be applied twice without duplicating rows. The release ID is
   stored in the snapshot properties and checked before writing.
5. Cost per release, measured on the synthetic data.

## Consequences

- No cloud table code is written until the spike result is recorded here.
- Gold tables carry the release ID so every row traces to a release.
- If Iceberg passes, this ADR names the writer and the catalog. If it fails,
  the cloud job loads BigQuery native tables and the other subprojects are
  unchanged.

## Revisit when

The spike fails, the catalog's pricing or support changes, or a consumer
cannot read the chosen format.
