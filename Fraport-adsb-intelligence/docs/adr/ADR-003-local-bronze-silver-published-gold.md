# ADR-003: Local Bronze and Silver, published Gold

**Status:** Accepted. The local feature and training handoff was clarified on
2026-11-23.

## Context

Earlier drafts placed Bronze and Silver in Cloud Storage and ran the
transformation as a Cloud Run Job. Two facts change that:

- The dataset is small. The busiest benchmark day, 2026-07-15, scales to about 55 GB of
  Parquet for two years. That fits on one machine, and DuckDB processes it
  without a cluster.
- The raw research data is the programme's source of record. Keeping it in
  one place under local control is simpler than keeping cloud copies in step.

The cloud side should still do real engineering work, not just store files.

## Decision

```text
LOCAL   Bronze (01) -> Silver (02) -> Gold (02) -> Release Gate -> Parquet release
LOCAL   Silver observations + approved release -> DuckDB features (04) -> Python/MLflow (05)
CLOUD   Approved release -> GCS Landing -> BigQuery managed Iceberg -> analytics (03)
```

1. **Bronze and Silver stay local.** Python and DuckDB build Silver. The CLI
   and batch scripts run today. Phase 07 adds local Dagster orchestration.
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
7. **Keep flight-level outcome labels and their coverage.** Project 04 builds
   prediction features separately from local observations and enforces the
   cutoff and availability rules. The local training input pins the Gold
   release ID, manifest hash, feature version and artifact checksums.

## Rationale

- Right-sized compute: a single machine handles the data, so a cluster would
  add cost and operations without benefit.
- A release is easy to verify, version and reproduce from a release ID.
- The cloud path demonstrates validation, idempotent loading, managed Iceberg
  and analytics. Local training and orchestration can use the pinned files.
- Forks can run the whole flow with synthetic data and their own GCP project.

## Consequences

- Subproject 02 moves to the local machine. Silver, Gold and the Release Gate
  live there. The code is containerised so the same logic can run in CI.
- Subproject 01 has no cloud upload.
- Project 03 consumes approved Gold releases. Project 04 combines local
  observations with release labels. Projects 05 and 06 take the training
  artifact and versioned model respectively.
- The cloud cannot recompute Silver. Changing Silver means a new local run and
  a new release.
- Real-data runs in the cloud cover only what Gold contains. Synthetic data
  covers everything else.

## Revisit when

- A use case needs row-level data in the cloud that Gold cannot supply.
- The data grows beyond what one machine can process.
