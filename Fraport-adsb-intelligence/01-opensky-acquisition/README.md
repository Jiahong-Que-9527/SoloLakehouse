# 01 · OpenSky Acquisition

**Runtime:** WSL Ubuntu. Data stays on this machine, backed up to a second disk.

Build a reliable, reproducible tool that collects two years of OpenSky state
vectors for a 75 km region around `EDDF` and keeps them as a traceable Parquet
dataset. The deliverable is the tool plus the dataset, ready for later
lakehouse ETL. It is not a cloud deployment.

## Status (2026-11-16)

Gate G0 has passed. Milestones M0 to M2 are done and are on `main`
(pull requests #123 to #125). Batches **b01 (2026-10)** through **b32 (2024-03)**
are accepted and backed up. b01 through b12 completed the twelve-month cut
line from 2025-11 through 2026-10. b24 finishes the original two-year window.
The next session collects batch **b33 (2024-02)**. Do not start b34 until
b33 is published.

Collected data is local, under `/home/bill/slh-data/aviation`, and is not in
git.

- State vectors, `eddf_r75km` v1: all hours of 2026-10 through 2024-03.
- Flights, `eddf_flights` v1: 2026-10-01 through 2026-11-01, and all of
  2026-09 through 2024-03.
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
- Batch b04: 102,748,798 state-vector rows, 1.95 GB, 33,852 flights. Validation
  outcome `passed` (720/720 hours, 0 problems, 0 anomalies). Accepted and
  published (`copied: 1502`, `checked: 750`).
  Report: `reports/batches/b04/report.md`.
- Batch b05: 120,648,884 state-vector rows, 2.26 GB, 39,580 flights. Validation
  outcome `passed` (720/720 hours, 0 problems, 0 anomalies). Accepted and
  published (`copied: 1502`, `checked: 750`).
  Report: `reports/batches/b05/report.md`.
- Batch b06: 121,391,958 state-vector rows, 2.26 GB, 40,021 flights. Validation
  outcome `passed` (744/744 hours, 0 problems, 0 anomalies). The processing
  change is flagged on 2026-08-13T12, 2026-08-14T08, and flight days 2026-08-13
  and 2026-08-14; those records stay `complete`. Accepted and published
  (`copied: 1552`, `checked: 775`).
  Report: `reports/batches/b06/report.md`.
- Batch b07: 113,094,102 state-vector rows, 2.15 GB, 38,682 flights. Validation
  outcome `passed` (720/720 hours, 0 problems, 0 anomalies). Accepted and
  published (`copied: 1502`, `checked: 750`).
  Report: `reports/batches/b07/report.md`.
- Batch b08: 115,582,748 state-vector rows, 2.18 GB, 40,416 flights. Validation
  outcome `passed` (741 complete hours, 2 `source_gap` hours, 1 `empty` hour,
  0 problems, 0 anomalies). `2026-05-22T08` and `2026-05-24T22` are global
  holes that are not on the OpenSky known-gaps page. `2026-05-25T21` is empty
  inside the EDDF box. Accepted and published (`copied: 1549`, `checked: 772`).
  Report: `reports/batches/b08/report.md`.
- Batch b09: 102,717,025 state-vector rows, 1.85 GB, 33,987 flights. Validation
  outcome `review` for two populated 01:00 UTC hours, 2026-03-13 (1,548 rows)
  and 2026-03-17 (1,292 rows). Every hour is complete. Accepted and published
  (`copied: 1552`, `checked: 775`).
  Report: `reports/batches/b09/report.md`.
- Batch b10: 84,895,854 state-vector rows, 1.51 GB, 28,405 flights. Validation
  outcome `review` for two populated hours on 2026-02-18, 01:00 (2,400 rows)
  and 02:00 (2,603 rows). Every hour is complete. Accepted and published
  (`copied: 1402`, `checked: 700`).
  Report: `reports/batches/b10/report.md`.
- Batch b11: 99,472,643 state-vector rows, 1.80 GB, 33,863 flights. Validation
  outcome `passed` (744/744 hours, 0 problems, 0 anomalies). Accepted and
  published (`copied: 1552`, `checked: 775`).
  Report: `reports/batches/b11/report.md`.
- Batch b12: 103,472,219 state-vector rows, 1.85 GB, 35,562 flights. Validation
  outcome `review` for one populated midnight hour, 2025-11-25T00 (4,670 rows
  against a Tuesday 00:00 median of 35,292). Every hour is complete. Accepted
  and published (`copied: 1502`, `checked: 750`). This batch finishes the
  twelve-month cut line.
  Report: `reports/batches/b12/report.md`.
- Batch b13: 120,362,843 state-vector rows, 2.23 GB, 41,349 flights. Validation
  outcome `passed` (744/744 hours, 0 problems, 0 anomalies). Accepted and
  published (`copied: 1552`, `checked: 775`).
  Report: `reports/batches/b13/report.md`.
- Batch b14: 123,070,660 state-vector rows, 2.28 GB, 41,225 flights. Validation
  outcome `passed` (720/720 hours, 0 problems, 0 anomalies). Accepted and
  published (`copied: 1502`, `checked: 750`).
  Report: `reports/batches/b14/report.md`.
- Batch b15: 119,685,125 state-vector rows, 2.34 GB, 42,224 flights. Validation
  outcome `passed` (744/744 hours, 0 problems, 0 anomalies). Accepted and
  published (`copied: 1552`, `checked: 775`).
  Report: `reports/batches/b15/report.md`.
- Batch b16: 109,673,473 state-vector rows, 2.21 GB, 41,821 flights. Validation
  outcome `passed` (744/744 hours, 0 problems, 0 anomalies). The benchmark day
  2025-07-15 was already committed and was skipped. Accepted and published
  (`copied: 1552`, `checked: 775`).
  Report: `reports/batches/b16/report.md`.
- Batch b17: 102,202,707 state-vector rows, 2.11 GB, 40,588 flights. Validation
  outcome `passed` (720/720 hours, 0 problems, 0 anomalies). Accepted and
  published (`copied: 1502`, `checked: 750`).
  Report: `reports/batches/b17/report.md`.
- Batch b18: 110,414,775 state-vector rows, 2.11 GB, 38,658 flights. Validation
  outcome `passed` (744/744 hours, 0 problems, 0 anomalies). Accepted and
  published (`copied: 1552`, `checked: 775`).
  Report: `reports/batches/b18/report.md`.
- Batch b19: 106,737,212 state-vector rows, 1.98 GB, 35,918 flights. Validation
  outcome `passed` (720/720 hours, 0 problems, 0 anomalies). Accepted and
  published (`copied: 1502`, `checked: 750`).
  Report: `reports/batches/b19/report.md`.
- Batch b20: 94,835,855 state-vector rows, 1.83 GB, 34,604 flights. Validation
  outcome `passed` (744/744 hours, 0 problems, 0 anomalies). 2025-03-10 is a
  thin but complete day: 1,470,301 state-vector rows and 113 flights. Accepted
  and published (`copied: 1552`, `checked: 775`).
  Report: `reports/batches/b20/report.md`.
- Batch b21: 76,460,404 state-vector rows, 1.51 GB, 29,561 flights. Validation
  outcome `review` for one populated early-morning hour, 2025-02-08T01 (1,094
  rows against a Saturday 01:00 median of 4,412). Every hour is complete.
  Accepted and published (`copied: 1402`, `checked: 700`).
  Report: `reports/batches/b21/report.md`.
- Batch b22: 75,211,438 state-vector rows, 1.53 GB, 30,174 flights. Validation
  outcome `review` for one populated early-morning hour, 2025-01-08T01 (501
  rows against a Wednesday 01:00 median of 2,741). Every hour is complete. The
  benchmark day 2025-01-15 was already committed and was skipped. Accepted and
  published (`copied: 1552`, `checked: 775`).
  Report: `reports/batches/b22/report.md`.
- Batch b23: 76,273,462 state-vector rows, 1.54 GB, 32,449 flights. Validation
  outcome `passed` (744/744 hours, 0 problems, 0 anomalies). Accepted and
  published (`copied: 1552`, `checked: 775`).
  Report: `reports/batches/b23/report.md`.
- Batch b24: 79,196,910 state-vector rows, 1.62 GB, 34,142 flights. Validation
  outcome `passed` (720/720 hours, 0 problems, 0 anomalies). The benchmark day
  2024-11-15 was already committed and was skipped. Accepted and published
  (`copied: 1502`, `checked: 750`). This batch finishes the two-year window.
  Report: `reports/batches/b24/report.md`.
- Batch b25: 103,257,913 state-vector rows, 2.05 GB, 37,197 flights. Validation
  outcome `review` for one populated early-morning hour, 2024-10-31T02 (5,683
  rows against a Thursday 02:00 median of 22,805). 2024-10-19 has 6,346,542
  rows and 837 flights; the day stays under the Parquet, query-time and scan
  limits and was accepted on review. Accepted and published
  (`copied: 1552`, `checked: 775`).
  Report: `reports/batches/b25/report.md`.
- Batch b26: 102,662,366 state-vector rows, 2.08 GB, 39,219 flights. Validation
  outcome `passed` (720/720 hours, 0 problems, 0 anomalies). Accepted and
  published (`copied: 1502`, `checked: 750`).
  Report: `reports/batches/b26/report.md`.
- Batch b27: 102,590,636 state-vector rows, 2.12 GB, 39,699 flights. Validation
  outcome `passed` (744/744 hours, 0 problems, 0 anomalies). Accepted and
  published (`copied: 1552`, `checked: 775`).
  Report: `reports/batches/b27/report.md`.
- Batch b28: 104,000,793 state-vector rows, 2.15 GB, 39,625 flights. Validation
  outcome `passed` (744/744 hours, 0 problems, 0 anomalies). Accepted and
  published (`copied: 1552`, `checked: 775`).
  Report: `reports/batches/b28/report.md`.
- Batch b29: 102,027,738 state-vector rows, 2.09 GB, 37,438 flights. Validation
  outcome `passed` (720/720 hours, 0 problems, 0 anomalies). 2024-06-26 has
  8,621,015 rows, 118 MB and 190 flights; the extra rows are other aircraft
  inside the box. Accepted and published (`copied: 1502`, `checked: 750`).
  Report: `reports/batches/b29/report.md`.
- Batch b30: 95,807,540 state-vector rows, 1.97 GB, 37,443 flights. Validation
  outcome `review` for one populated hour immediately before the documented
  gap, 2024-05-20T09 (17,912 rows against a Monday 09:00 median of 179,437).
  19 hours are `source_gap` (2024-05-20T10 through 2024-05-21T04). Flight
  days 2024-05-20 and 2024-05-21 are complete with 343 and 819 flights.
  Accepted and published (`copied: 1533`, `checked: 756`).
  Report: `reports/batches/b30/report.md`.
- Batch b31: 95,095,454 state-vector rows, 1.92 GB, 36,856 flights. Validation
  outcome `passed` (720/720 hours, 0 problems, 0 anomalies). Accepted and
  published (`copied: 1502`, `checked: 750`).
  Report: `reports/batches/b31/report.md`.
- Batch b32: 92,374,398 state-vector rows, 1.75 GB, 33,171 flights. Validation
  outcome `review` for one populated early-morning hour, 2024-03-14T01 (1,257
  rows against a Thursday 01:00 median of 5,772). Every hour is complete.
  Accepted and published (`copied: 1552`, `checked: 775`).
  Report: `reports/batches/b32/report.md`.
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

1. Collect b33, February 2024. This is a leap month (29 days, 696 hours).
   State vectors: `run --from 2024-02-01T00:00:00Z --until 2024-03-01T00:00:00Z`.
   Flights: `collect-flights --from 2024-02-01 --until 2024-03-01`.
2. `validate --batch b33`, `report --batch b33`, then `accept` and `publish`.
   A validation outcome of `review` needs `--notes`. A `failed` outcome stops
   the gate. Stop the backfill if a day exceeds 6 million rows, 100 MB of
   Parquet, 60 seconds per hour, or 5 GB scanned per hour. Do not start b34
   until b33 is published.
3. Leave `serials` out. Do not upload Bronze. Do not recollect b01–b32.
   Commit only when asked.

`OPENSKY_USERNAME` must be set. If a run stops with `AUTH_REQUIRED`, run
`opensky-ingest login` and resume the same range. Do not print the username,
the token, or the login URL.

Silver for the pilot week (vertical slice V0 in the project plan) can start
in parallel. It is not the next acquisition step. ADR-001 to ADR-003 are
still Proposed. ADR-004 stays blocked on its spike.

## Documents

- [Design](docs/design.md): storage layout, dataset contract, commit protocol,
  validation, publishing and tool structure.
- [Batch plan](docs/batch-plan.md): pilot, 24 collected batches, the
  five-year extension (b25–b60, not started), gates and the session routine.
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
| Period | `[2021-11-01, 2026-11-01)` UTC, 43,824 hours. b01–b24 are collected; b25–b60 extend the start back to 2021-11 |
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
