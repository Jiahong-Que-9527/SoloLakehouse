# ECB Delta Lakehouse

<!-- [房玄龄·2026-11-15] Define the D01 to D04 project brief. -->

**Milestones:** D01 to D04 in the [Databricks roadmap](../README.md). Planned.

Build a versioned financial data product from one ECB daily reference
exchange-rate series. Use a fixed quarter for the first sample, then run
the same transformations on a larger window when there is a downstream
training use case.

## Data contract

- **Input:** ECB `EXR.D.USD.EUR.SP00.A`. Record the series key, observation
  date, source units, input window and source provenance. Test missing
  dates against the publication calendar.
- **Bronze** keeps the source batch and ingestion metadata.
- **Silver** keeps one current observation per series key and date.
  Synthetic revision fixtures carry an explicit ordering field.
- **Gold** publishes day-to-day changes and rolling volatility under a
  versioned schema. The consumer selects a release and Delta version.
  Define the observation count and missing-day treatment for rolling metrics.

## Milestone acceptance

- **D01 · Reproduce the tables.** A small fixture produces fixed Silver keys
  and known Gold values. A repeat run keeps those results stable.
- **D02 · Deploy the job.** A project Bundle deploys ingest, transform and
  validation tasks. Verify that a failed validation task blocks release
  and that recovery produces one accepted release.
- **D03 · Reconcile incremental output.** Process successive files with new,
  corrected and duplicated observations. Restart with the existing
  checkpoint. Confirm that stale input cannot replace a newer observation
  and that the final result matches a full recomputation. Auto Loader
  handles file ingestion, while the update logic handles revision order.
- **D04 · Verify access and release evidence.** Verify a Gold reader, verify
  a denied access case, and link the accepted release to the Delta version,
  source window, validation result and Git commit. Record lineage evidence
  when available in the test workspace.

The resulting Gold snapshot is the input for the planned financial ML
workload. A consumer fixture uses the same schema for independent tests.

[ECB series documentation](https://data.ecb.europa.eu/data/datasets/EXR/EXR.D.USD.EUR.SP00.A) ·
[Databricks Auto Loader](https://docs.databricks.com/gcp/en/ingestion/cloud-object-storage/auto-loader/file-events-explained)
