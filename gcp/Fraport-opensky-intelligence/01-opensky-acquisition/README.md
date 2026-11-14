# 01 · OpenSky Acquisition

**Runtime:** WSL Ubuntu, with Google Cloud Storage as the shared copy.

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
| Dataset | `eddf_r75km` v1 |
| Source | OpenSky Trino, `state_vectors_data4` |
| Region | About 150 km square around EDDF (49.36–50.71 N, 7.52–9.62 E) |
| Period | `[2024-11-01, 2026-11-01)` UTC, 17,520 hours |
| Format | Parquet, ZSTD, explicit schema, one file per hour |
| Layout | `dt=YYYY-MM-DD/hour-HH.parquet` |
| Local root | `/home/bill/slh-data/aviation` (outside the repository) |
| Backup | `/mnt/e/slh-backup/aviation` |
| Size | About 31 GB Parquet (estimate, to be measured in the pilot) |

Bronze keeps source columns with their original meaning and units. It does not
filter, clean, deduplicate or interpolate.

## Approach

1. **Pilot.** One week, reconciled against the source and the legacy fin
   receipts, with a deliberate interruption and resume test.
2. **Monthly batches.** Twenty-four batches. The first four cover all seasons.
   The rest run newest to oldest.
3. **Per-batch record.** Hour manifests, a batch manifest, a report, ledger
   events and an acceptance record.
4. **Publish.** Verified backup after acceptance. GCS upload after OpenSky
   confirms that cloud storage is allowed.

## Scope

| Capability | Status |
|------------|--------|
| OpenSky Trino connection with OAuth login | Required |
| CLI and configuration files | Required |
| Hourly collection with retry and resume | Required |
| Parquet with explicit schema | Required |
| Hour and batch manifests with checksums | Required |
| Validation, reconciliation and batch reports | Required |
| pytest and GitHub Actions CI | Required |
| Local backup and verification | Required |
| GCS upload | Required, gated on OpenSky approval |
| DuckDB catalog and manifest export | Recommended |
| Docker | Optional |
| Cloud Run, Cloud Scheduler, Kubernetes | Out of scope |

## Acceptance

- A repeat run produces no duplicate files and no changed manifests.
- An interrupted run resumes from the last committed hour.
- Empty hours, failed hours and documented source gaps are kept distinct.
- Every committed file has a manifest with rows, size, checksum, SQL hash,
  schema version and source commit.
- Every batch has a report and an acceptance record before it is published.
- The dataset summary lists expected, complete, empty, gap-flagged and failed
  hours.
- A restore from backup and from GCS reproduces the manifest hashes.

## Risks

- **Licence and eligibility.** OpenSky's free Trino access targets
  non-profit research and education, forbids passing data on, and requires
  deletion when the research ends. Ask OpenSky before the monthly batches and
  before any cloud upload.
- **Volume and load.** Row counts and scan size for the large region are
  estimates. The pilot decides.
- **Login expiry.** Sessions last a few days and need a manual login.
- **Source changes.** Two documented data gaps and one decoder change fall in
  the window.

## Outputs for later projects

An accepted Bronze dataset, manifests, a dataset contract and a dataset
summary. Project 02 reads the accepted hours through the manifests.
