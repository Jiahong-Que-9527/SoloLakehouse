# 01 · OpenSky Acquisition

**Runtime:** Local, with Google Cloud Storage as the shared data store.

Build a reliable, reproducible tool that downloads historical OpenSky state
vectors for `EDDF` and keeps them as a traceable local Parquet dataset. The
deliverable is the tool plus a documented one-year dataset, not a cloud
deployment.

## Why local

The task is a one-time historical backfill limited by OpenSky Trino query
speed, not by local compute. See
[ADR-001](../docs/adr/ADR-001-local-execution-for-historical-acquisition.md).

## Scope

| Capability | Status |
|------------|--------|
| OpenSky Trino connection | Required |
| CLI and configuration file | Required |
| Hourly batch download | Required |
| Parquet output with an explicit schema | Required |
| Retry and checkpoint | Required |
| Data manifest and checksum | Required |
| Tests and GitHub Actions CI | Required |
| GCS upload | Recommended |
| Docker | Optional |
| Cloud Run, Cloud Scheduler, Kubernetes | Out of scope |

## Design

- **Layout.** Hive-style partitions under a versioned dataset path:
  `bronze/opensky/state_vectors/v1/airport=EDDF/year=/month=/day=/hour-HH.parquet`.
- **Format.** Parquet with ZSTD, UTC time, one file per hour.
- **Versioning.** A change to the geographic bounds, fields or query logic
  that changes data meaning creates a new dataset version (`v2`).
- **State.** SQLite tracks batch status. The manifest records committed files.
  If SQLite is lost, rebuild its state from manifests and file checksums.
- **Query.** DuckDB reads the committed Parquet files for inspection.
- **Raw fields.** Keep source meaning, types and units. Do not drop missing
  callsigns, filter by `onground`, deduplicate or interpolate.

Planned data root, kept outside the repository:

```text
slh-data/aviation/
  bronze/opensky/state_vectors/v1/...
  metadata/{manifests, schemas, checkpoint.db, catalog.duckdb}
  staging/       in-flight downloads
  quarantine/    files that failed validation
  reports/       dataset summary
```

## Milestones

- **V0.1 Local dataset.** Download one day, write hourly Parquet and query it
  with DuckDB.
- **V0.2 Managed dataset.** Date partitions, explicit schema, SQLite
  checkpoint, manifest and checksum. Verify repeat runs and failure recovery.
- **V1.0 Annual data asset.** Measure seven days of size, backfill one month,
  complete the year, write the dataset summary, set up backup and restore and
  publish a run report.

## Planned interface

These commands describe the target interface. They are not implemented yet.

```text
opensky-ingest download --airport EDDF --start 2025-01-01 --end 2025-02-01
opensky-ingest status
opensky-ingest validate
opensky-ingest report
```

## Acceptance

- A repeat run produces no duplicate files or manifest entries.
- An interrupted run resumes from the last committed batch.
- Empty batches (query succeeded, zero rows) are distinct from failed batches.
- Every committed file has a manifest entry with row count, size, checksum,
  schema version and source commit.
- The dataset summary reports expected, completed, empty and failed batches.

## Risks

- OpenSky Trino access, authentication and query limits.
- OpenSky terms on retention and cloud storage. Confirm before upload.
- Data volume. Estimate from a seven-day sample before buying storage.

## Outputs for later projects

A validated Bronze dataset, manifests and a dataset summary. Project 02 reads
them from GCS.
