# Batch plan

Run order, gates and session routine for collecting `eddf_r75km` v1 over
`[2024-11-01, 2026-11-01)`. See the [design](design.md) for the mechanics.
Durations are *estimates* until the pilot gives measured values.

## Units

- **Hour:** one query, one Parquet file, one manifest. 17,520 hours in total.
- **Batch:** one calendar month, about 720 hours. A batch can span several
  sessions and several days.
- **Session:** one `run` invocation, capped at about three hours to fit the
  OpenSky login lifetime.

## Pilot P0

Window: 2026-10-12 to 2026-10-18 UTC, seven days, 168 hours. The week lies in
the period covered by the legacy small-box receipts on fin.

Steps:

1. Collect one hour. Inspect rows, file size, scan bytes and query time.
2. Collect one day.
3. Collect the remaining six days.
4. Reconcile every hour against source aggregates.
5. Cross-check the inner small box against the fin receipts.
6. Interrupt a run on purpose, resume it, then repeat the whole week. Confirm
   no duplicates and no changed manifests.

Measure and record:

| Measure | Estimate | Review threshold |
|---------|----------|------------------|
| Rows per day | 3.5 M | above 6 M |
| Parquet per day | 43 MB | above 100 MB |
| Query time per hour | 8 to 12 s | above 60 s |
| Scan per hour | about 0.7 GB | above 5 GB |
| Hours failed | 0 | any unexplained |

If a threshold is crossed, stop and review options before more batches: a
smaller box, a shorter period, an altitude cut as a documented extraction rule,
or a conversation with OpenSky. Update the estimates in this document and in
the design with the measured values.

**Gate G0 (pilot accepted):** all hours committed, reconciliation matches,
cross-check matches or is explained, recovery test passed, measurements
recorded, OpenSky authorization reference stored in the dataset contract.

## Monthly batches

The first four batches give early coverage of all seasons. The rest run
newest to oldest.

| ID | Month | Why this order |
|----|-------|----------------|
| b01 | 2026-10 | Autumn. Overlaps legacy data for validation. Includes the pilot week |
| b02 | 2026-07 | Summer peak traffic |
| b03 | 2026-01 | Winter. Contains two documented source gaps |
| b04 | 2026-04 | Spring |
| b05 | 2026-09 | Newest remaining |
| b06 | 2026-08 | Contains the processing change on 2026-08-13 and 14 |
| b07 | 2026-06 | |
| b08 | 2026-05 | |
| b09 | 2026-03 | |
| b10 | 2026-02 | |
| b11 | 2025-12 | |
| b12 | 2025-11 | |
| b13 | 2025-10 | |
| b14 | 2025-09 | |
| b15 | 2025-08 | |
| b16 | 2025-07 | |
| b17 | 2025-06 | |
| b18 | 2025-05 | |
| b19 | 2025-04 | |
| b20 | 2025-03 | |
| b21 | 2025-02 | |
| b22 | 2025-01 | |
| b23 | 2024-12 | |
| b24 | 2024-11 | Oldest |

Hours already committed in the pilot are skipped in b01.

Estimated per batch: 2 to 3 hours of query time, about 1.3 GB of Parquet.
Estimated total: about 55 hours of query time and 31 GB. The calendar time
depends on how often you log in. Two to four weeks is realistic.

## Gate per batch

A batch moves on only when each step passes:

1. `run` finished with no pending hours, or with documented gap flags only.
2. `validate` passed with no unexplained anomalies.
3. `reconcile` matched the source on the sampled hours.
4. `report` written and reviewed.
5. `accept` recorded.
6. `publish --backup` verified. `--gcs` once cloud upload is allowed.

Early stop rules:

- Two batches in a row with unexplained validation failures: stop and review
  the design.
- Schema drift or a change in OpenSky behaviour: stop and record it.

## Session routine

1. Check free disk space and that `E:` is mounted.
2. `login` if the last session expired.
3. `status` to see what is pending.
4. `run --batch <id> --max-duration 3h`.
5. If the run stops with `AUTH_REQUIRED`, log in and continue. Nothing is lost.
6. When the batch has no pending hours: `validate`, `reconcile`, `report`,
   review, `accept`, `publish`.
7. Record any manual decision in the batch notes.

## Dataset sign-off

After b24 and a final `verify`:

- Dataset summary: expected, complete, empty, gap-flagged and failed hours,
  totals for rows and bytes, unique aircraft, per-month table.
- Restore test: recover a month from the `E:` backup and from GCS and compare
  hashes.
- Record the processing-epoch split and the known gaps in the summary.
- Record the OpenSky retention obligations and the review date.

## After the window

Later extensions are separate decisions:

- Incremental collection for hours older than 48 h, which fits a scheduled job
  only if unattended OpenSky login is solved.
- A second airport or a larger region, as a new dataset.
