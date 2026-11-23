# ADR-004: Gold table format and catalog

**Status:** Accepted (2026-11-21, spike passed). The local training handoff was
clarified on 2026-11-23.

## Context

Gold releases (ADR-003) land in Cloud Storage. They need to become managed
tables for BigQuery analytics, with rows traceable to the approved release.

The candidates are:

- **Apache Iceberg on GCS** with a Google-managed catalog. It gives snapshots,
  schema evolution and an open format.
- **BigQuery native tables** loaded from the release Parquet. Simplest, but
  the data is held in BigQuery storage.
- **Delta Lake** in Databricks was considered during the initial design.

The Google catalog service, its names, its regional availability, its engine
support for writes and the BigQuery integration have not been verified for
this programme.

## Decision

Use BigQuery managed Apache Iceberg on GCS for cloud Gold. The spike below
validated the choice. Subproject 04 consumes the approved local Gold Parquet
release and builds features in DuckDB. Parquet artifacts and manifests are
the local training handoff.

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

## Spike result (2026-11-21, europe-west3, project `slh-gcp-test`)

Ran on the real release `v002` (4,656 rows, 179.6 KB Parquet) with the
script in [03-airport-analytics/spike](../../03-airport-analytics/spike/),
log `run-20261121-europe-west3.log`. Actual measured cost of the run: €0
(63.6 MB bytes processed across all queries, 18.5 slot-seconds, inside the
BigQuery free tier).

1. **Catalog available in `europe-west3`: PASS.** A BigQuery managed
   Iceberg table (`CREATE TABLE … WITH CONNECTION … OPTIONS(table_format
   ='ICEBERG', storage_uri=…)`) was created and replaced successfully with
   a colocated `europe-west3` bucket and dataset, over a CLOUD_RESOURCE
   BigLake connection.
2. **BigQuery queries the Iceberg tables, locations compatible: PASS.** An
   aggregation over the table returned exactly the release manifest
   numbers (2,583 labeled of 4,656).
3. **Cheap writer: BigQuery DML itself.** `INSERT INTO` the managed
   Iceberg table loaded the release directly — no Cloud Run job and no
   Dataproc Serverless batch is needed for ingestion. (Dataproc Serverless
   was rejected during the spike because of per-batch minimum billing.)
4. **Idempotence: PASS.** The release-apply guard counts rows already
   carrying the release ID and skips the append; a repeated apply inserted
   0 rows and the row count stayed 4,656. **Deviation from the original
   wording:** the release ID is stored as a column (and cluster key) on
   every row and checked before writing; BigQuery DML on managed Iceberg
   tables cannot inject custom Iceberg snapshot properties, so the
   snapshot-level requirement is met at row level instead.
5. **Cost per release: €0 at pilot scale** (see above); storage is billed
   as Cloud Storage, queries as on-demand. The only non-free SKU is the
   automatic storage optimization (compaction/GC billed in DCU-seconds),
   which measured below €0.01 on this table size.

## Consequences

- The cloud Gold tables are BigQuery managed Iceberg tables on a colocated
  GCS bucket, written by BigQuery DML over a CLOUD_RESOURCE BigLake
  connection, in `europe-west3`.
- Gold tables carry the release ID as a column on every row, and the
  ingestion guard checks it before writing.
- Project 04 pins the original release manifest for feature and training
  reproducibility. The cloud table supports analytics on the same releases.

## Revisit when

The spike fails, the catalog's pricing or support changes, or a consumer
cannot read the chosen format.
