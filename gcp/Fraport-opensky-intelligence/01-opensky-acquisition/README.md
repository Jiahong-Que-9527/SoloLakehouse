# 01 · OpenSky Acquisition

**Runtime:** WSL Ubuntu. Data stays on this machine, backed up to a second disk.

Build a reliable, reproducible tool that collects two years of OpenSky state
vectors for a 75 km region around `EDDF` and keeps them as a traceable Parquet
dataset. The deliverable is the tool plus the dataset, ready for later
lakehouse ETL. It is not a cloud deployment.

## Documents

- [Design](docs/design.md): storage layout, dataset contract, commit protocol,
  validation, publishing and tool structure.
- [Batch plan](docs/batch-plan.md): pilot, 24 monthly batches, gates and the
  session routine.
- [ADR-001](../docs/adr/ADR-001-local-execution-for-historical-acquisition.md):
  why acquisition runs locally.
- [ADR-002](../docs/adr/ADR-002-regional-dataset-and-monthly-batches.md): why a
  regional dataset in monthly batches.

## Dataset

| Item | Value |
|------|-------|
| Datasets | `eddf_r75km` v1 (state vectors) and `eddf_flights` v1 (flights) |
| Source | OpenSky Trino, `state_vectors_data4` and `flights_data4` |
| Region | About 150 km square around EDDF (49.36–50.71 N, 7.52–9.62 E) |
| Period | `[2024-11-01, 2026-11-01)` UTC, 17,520 hours |
| Format | Parquet, ZSTD, explicit schema |
| Layout | State vectors `dt=YYYY-MM-DD/hour-HH.parquet`. Flights `dt=YYYY-MM-DD/flights.parquet` |
| `serials` column | Decided by a pilot A/B test before the monthly batches |
| Local root | `/home/bill/slh-data/aviation` (outside the repository) |
| Backup | `/mnt/e/slh-backup/aviation` |
| Size | State vectors: 71 MB on 2026-10-15, about 52 GB for two years. Flights: 7.4 MB a day in the pilot week, about 5.4 GB for 731 days |

Bronze keeps source columns with their original meaning and units. It does not
filter, clean, deduplicate or interpolate.

## Approach

1. **Discovery and benchmark.** Read-only schema and availability checks, a
   pilot week reconciled against the source and the legacy fin receipts, five
   benchmark days across seasons, a `serials` A/B test, and a deliberate
   interruption and resume test.
2. **Monthly batches.** Twenty-four batches, each with state-vector hours and
   flight days. The first four cover all seasons, then newest to oldest. The
   first twelve give twelve complete months.
3. **Per-batch record.** Hour manifests, a batch manifest, a report, ledger
   events and an acceptance record.
4. **Publish.** Verified backup to the second disk after acceptance. Bronze
   is not uploaded to the cloud.

## Scope

| Capability | Status |
|------------|--------|
| OpenSky Trino connection with OAuth login | Required |
| State vectors and flights datasets | Required |
| Discovery and benchmark report | Required |
| CLI and configuration files | Required |
| Hourly collection with retry and resume | Required |
| Parquet with explicit schema | Required |
| Hour and batch manifests with checksums | Required |
| Validation, reconciliation and batch reports | Required |
| pytest and GitHub Actions CI | Required |
| Local backup and verification | Required |
| DuckDB catalog and manifest export | Recommended |
| Docker | Optional |
| Cloud upload of Bronze, Cloud Run, Cloud Scheduler, Kubernetes | Out of scope |

## Acceptance

- A repeat run produces no duplicate files and no changed manifests.
- An interrupted run resumes from the last committed hour.
- Empty hours, failed hours and documented source gaps are kept distinct.
- Every committed file has a manifest with rows, size, checksum, SQL hash,
  schema version and source commit.
- Every batch has a report and an acceptance record before it is published.
- The dataset summary lists expected, complete, empty, gap-flagged and failed
  hours.
- A restore from the backup reproduces the manifest hashes.

## Risks

- **Interrupted collection.** The batch plan runs the most valuable months
  first and backs up each accepted batch.
- **Volume and load.** Row counts and scan size for the large region are
  estimates. The pilot decides.
- **Login expiry.** Sessions last a few days and need a manual login.
- **Source changes.** Two documented data gaps and one decoder change fall in
  the window.

## Outputs for later projects

An accepted Bronze dataset, manifests, a dataset contract and a dataset
summary. Project 02 reads the accepted hours through the manifests, on this
machine.
