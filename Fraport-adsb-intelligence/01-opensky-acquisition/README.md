# 01 · OpenSky Acquisition

**Runtime:** WSL Ubuntu. Data stays on this machine, backed up to a second disk.

Build a reliable, reproducible tool that collects two years of OpenSky state
vectors for a 75 km region around `EDDF` and keeps them as a traceable Parquet
dataset. The deliverable is the tool plus the dataset, ready for later
lakehouse ETL. It is not a cloud deployment.

## Status (2026-11-15)

Gate G0 has passed. Milestones M0 to M2 are done and are on `main`
(pull requests #123 to #125). Batches **b01 (2026-10)**, **b02 (2026-07)** and
**b03 (2026-01)** are accepted and backed up. The next session collects batch
**b04 (2026-04)**. Do not start b05.

Collected data is local, under `/home/bill/slh-data/aviation`, and is not in
git.

- State vectors, `eddf_r75km` v1: all 744 hours of 2026-10, 2026-07 and
  2026-01, plus benchmark days 2024-11-15, 2025-01-15 and 2025-07-15.
- Flights, `eddf_flights` v1: 2026-10-01 through 2026-11-01, all of 2026-07
  and of 2026-01, plus the three benchmark days above.
- Batch b01: 109,641,931 state-vector rows, 2.13 GB, 40,844 flights. Validation
  outcome `review` for six early-morning hours after the 2026-10-25 clock
  change; every hour is complete. Accepted and published.
  Report: `reports/batches/b01/report.md`.
- Batch b02: 121,955,581 state-vector rows, 2.33 GB, 40,596 flights. Validation
  outcome `passed` (744/744 hours, 0 problems, 0 anomalies). Accepted and
  published (`copied: 1552`, `checked: 775`).
  Report: `reports/batches/b02/report.md`.
- Batch b03: 89,882,973 state-vector rows, 1.53 GB, 26,637 flights. Validation
  outcome `passed` (714 complete hours, 30 `source_gap` hours, 0 problems,
  0 anomalies). Flight days 2026-01-02, 2026-01-03 and 2026-01-24 are
  `source_gap`: each flights partition is empty because a documented gap
  overlaps that day. Accepted and published (`copied: 1519`, `checked: 742`).
  Report: `reports/batches/b03/report.md`.
- Hour reconciliation matched 168/168:
  `reports/reconcile/20261114T221544Z-3852.json`.
- The fin small-box cross-check matched 168/168 (latitude 49.98–50.07,
  longitude 8.48–8.62): `reports/cross-check/20261114T223121Z-dde3.json`.
- Benchmark report: [docs/benchmark-report.md](docs/benchmark-report.md). The
  busiest day, 2026-07-15, is under every review threshold. Two years scales
  to about 55 GB and 19 hours of query time.
- `serials` stays out of v1. The 2026-07-15 comparison is in
  `reports/serials-ab/2026-07-15/`.
- Recovery: `2024-11-15T00` was interrupted after the Parquet file was
  published and before the manifest. Resume quarantined that file, committed
  the hour again with the same SHA256, and a repeat run left the day's
  manifests unchanged.

The CLI has `login`, `discover`, `collect-hour`, `run`, `collect-flights`,
`reconcile`, `cross-check`, `validate`, `report`, `accept` and `publish`.
`publish` copies an accepted batch to `/mnt/e/slh-backup/aviation` and checks
SHA256. There is no GitHub Actions workflow yet.

Next session:

1. Collect b04, April 2026. State vectors:
   `run --from 2026-04-01T00:00:00Z --until 2026-05-01T00:00:00Z`.
   Flights: `collect-flights --from 2026-04-01 --until 2026-05-01`.
2. `validate --batch b04`, `report --batch b04`, then `accept` and `publish`.
   A validation outcome of `review` needs `--notes`. A `failed` outcome stops
   the gate. Stop the backfill if a day exceeds 6 million rows, 100 MB of
   Parquet, 60 seconds per hour, or 5 GB scanned per hour.
3. Leave `serials` out. Do not upload Bronze. Commit only when asked.

`OPENSKY_USERNAME` must be set. If a run stops with `AUTH_REQUIRED`, run
`opensky-ingest login` and resume the same range. Do not print the username,
the token, or the login URL.

Silver for the pilot week (vertical slice V0 in the project plan) can start
in parallel. It is not the next acquisition step. ADR-001 to ADR-003 are
still Proposed. ADR-004 stays blocked on its spike.

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
| `serials` column | Excluded from v1 after the 2026-07-15 A/B test |
| Local root | `/home/bill/slh-data/aviation` (outside the repository) |
| Backup | `/mnt/e/slh-backup/aviation` |
| Size | State vectors: 75 MB on the busiest benchmark day (2026-07-15), about 55 GB for two years. Flights: about 7 MB a day, about 5.4 GB for 731 days |

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
