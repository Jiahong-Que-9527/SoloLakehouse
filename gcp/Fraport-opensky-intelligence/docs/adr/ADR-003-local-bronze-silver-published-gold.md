# ADR-003: Local Bronze and Silver, published Gold

**Status:** Proposed

## Context

Earlier drafts placed Bronze and Silver in Cloud Storage and ran the
transformation as a Cloud Run Job. Two facts change that:

- The dataset is small. About 31 GB of Parquet for two years fits on one
  machine, and DuckDB processes it without a cluster.
- The raw research data is the programme's source of record. Keeping it in
  one place under local control is simpler than keeping cloud copies in step.

The cloud side should still do real engineering work, not just store files.

## Decision

```text
LOCAL   Bronze (01) -> Silver (02) -> Gold (02) -> Release Gate -> release
CLOUD   GCS Landing -> validation -> Gold tables -> BigQuery -> models
```

1. **Bronze and Silver stay local.** Python and DuckDB build Silver. Local
   orchestration is a CLI and batch scripts. No Dagster and no local Iceberg.
2. **Gold is built locally and published.** Gold holds the flight-level and
   hourly products that later projects need. Only Gold crosses the boundary.
3. **The Release Gate is the interface.** A release is an immutable, versioned
   folder:

   ```text
   releases/<product>/v001/
     data/part-0001.parquet
     manifest.json     files, rows, sizes, SHA256, release ID, source commit
     contract.yaml     schema, grain, keys, field policy, quality thresholds
     validation.json   results of the gate checks
     approval.json     who approved the release, when, with notes
     _SUCCESS          written last, after every other file is verified
   ```

4. **The gate checks** schema against the contract, row counts, checksums,
   quality thresholds and the field policy. The field policy lists which
   columns are exported and whether identifiers such as `icao24` or `callsign`
   are kept, hashed or dropped. A failed check blocks the upload and is
   recorded.
5. **The cloud ingests releases.** A private Landing bucket receives releases
   with a create-only upload and a least-privilege identity. Cloud jobs
   validate the manifest and contract, then materialise Gold tables. The same
   release can be ingested twice without duplicating rows. The table format
   is decided in [ADR-004](ADR-004-gold-table-format-and-catalog.md).
6. **Cloud cannot reach Bronze or Silver.** The upload identity can only write
   to Landing.
7. **Gold must carry flight-level features.** An hourly aggregate alone would
   make the Taxi-in model impossible. The Gold contract must include the
   per-flight features and labels, with label coverage.

## Rationale

- Right-sized compute: a single machine handles the data, so a cluster would
  add cost and operations without benefit.
- A release is easy to verify, version and reproduce from a release ID.
- The cloud still demonstrates validation, idempotent loading, table
  management, analytics, training and orchestration.
- Forks can run the whole flow with synthetic data and their own GCP project.

## Consequences

- Subproject 02 moves to the local machine. Silver, Gold and the Release Gate
  live there. The code is containerised so the same logic can run in CI.
- Subproject 01 has no cloud upload.
- Subprojects 03 to 06 consume Gold releases, not Bronze or Silver.
- The cloud cannot recompute Silver. Changing Silver means a new local run and
  a new release.
- Real-data runs in the cloud cover only what Gold contains. Synthetic data
  covers everything else.

## Revisit when

- A use case needs row-level data in the cloud that Gold cannot supply.
- The data grows beyond what one machine can process.
