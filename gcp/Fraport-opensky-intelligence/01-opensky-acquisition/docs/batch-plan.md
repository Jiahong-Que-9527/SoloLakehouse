# Batch plan

Run order, gates and session routine for collecting `eddf_r75km` v1 (state
vectors) and `eddf_flights` v1 over `[2024-11-01, 2026-11-01)`. See the
[design](design.md) for the mechanics. Durations are *estimates* until the
pilot gives measured values.

## Schedule

Target calendar, to be adjusted after the pilot:

| Dates | Work |
|-------|------|
| Nov 15 to 21 | Build M0 and M1. Build `discover` first and run it as soon as it exists |
| Nov 22 to 25 | Discovery, pilot week, benchmark days, `serials` A/B test, gate G0 |
| Nov 26 to Dec 20 | Batches b01 to b24, about one batch per working day, one login every few days |
| Dec 21 to 31 | Buffer, remaining flight days, `verify`, backups, dataset summary |

Nothing is uploaded to the cloud from this subproject. Bronze stays local
and is backed up to `E:`.

Protect the work against an interrupted collection:

- **Cut line.** b01 to b12 give twelve complete months (2025-11 to 2026-10) and
  all seasons. They run first. b13 to b24 add the second year.
- **Back up each batch when accepted.** Do not leave backups for the end.

## Units

- **Hour:** one query, one Parquet file, one manifest. 17,520 hours in total.
- **Flight day:** one `flights_data4` day partition, one query, one file, one
  manifest. 731 days in total.
- **Batch:** one calendar month, about 720 hours. A batch can span several
  sessions and several days.
- **Session:** one `run` invocation, capped at about three hours to fit the
  OpenSky login lifetime.

## Discovery, pilot and benchmark

Everything here must finish and pass gate G0 before the monthly batches.

### D0: discovery (read only)

1. List the tables available to the account.
2. `DESCRIBE` `state_vectors_data4` and `flights_data4`. Compare with the
   documented schemas and fix the Arrow types, including `serials` and the
   nested flight columns.
3. Probe that hour partitions exist at several points across the window,
   starting with 2024-11, and that `flights_data4` has day partitions there.
4. Check the Trino scan and queue behaviour with one cheap query.

Output: a schema record and an availability record. Stop if anything in the
window is unavailable.

### P0: pilot week

Window: 2026-10-12 to 2026-10-18 UTC, seven days, 168 hours. The week lies in
the period covered by the legacy small-box receipts on fin.

1. Collect one hour. Inspect rows, file size, scan bytes and query time.
2. Collect one day.
3. Collect the remaining six days, plus the seven flight days.
4. Reconcile every hour against source aggregates.
5. Cross-check the inner small box against the fin receipts.
6. Interrupt a run on purpose, resume it, then repeat the whole week. Confirm
   no duplicates and no changed manifests.

### B0: benchmark days

Collect one full day for each date, state vectors and flights:

| Date | Why |
|------|-----|
| 2024-11-15 | Start of the window, tests old data availability |
| 2025-01-15 | Winter operations |
| 2025-07-15 | Summer peak |
| 2026-07-15 | Second-year summer, before the OpenSky processing change |
| 2026-10-15 | Recent data after the processing change (inside the pilot week) |

For every day record: rows, query duration, download duration, Parquet size,
distinct aircraft, null positions, ground rows, minimum and maximum event time,
peak memory. The benchmark report is a deliverable of this subproject. It
replaces the estimates in the design.

### S0: `serials` A/B test

On one benchmark day collect the state vectors twice, with and without
`serials`. Compare Parquet size, query time, download time and memory. Record
the decision and the reasons in the dataset contract. If `serials` is included
and the pilot week was collected without it, collect the pilot week again.

### Measurements and thresholds

| Measure | Earlier estimate | Measured 2026-10-15 | Review threshold |
|---------|------------------|---------------------|------------------|
| Rows per day | 3.5 M | 3.64 M | above 6 M |
| Parquet per day | 43 MB | 71 MB | above 100 MB |
| Query time per hour | 8 to 12 s | 1.7 to 7.5 s | above 60 s |
| Scan per hour | about 0.7 GB | 0.53 to 1.15 GB | above 5 GB |
| Hours failed | 0 | 0 | any unexplained |

`2026-10-15` is under every review threshold: 24 committed hours, 3,640,281
rows, 71 MB of Parquet, 90 s of query time, 19.6 GB scanned, 2,296 distinct
aircraft, no duplicate keys. The query keeps only rows with a position inside
the box, so null positions are absent by construction. If the other pilot days
stay near this one, a 30-day month is about 2.1 GB and 45 minutes of query
time, and the two-year set is about 52 GB and 18 hours of query time.

If a threshold is crossed, stop and review options before more batches: a
smaller box, a shorter period, an altitude cut as a documented extraction rule,
or a conversation with OpenSky. Replace the measured column when a later day
differs.

**Gate G0 (pilot accepted):** discovery recorded, all pilot hours committed,
reconciliation matches, cross-check matches or is explained, recovery test
passed, benchmark report written, `serials` decision recorded.

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

Hours and flight days already committed in the pilot and benchmark are skipped.
Each batch collects its state-vector hours first, then the flight days whose
source `day` falls in the same month. The last flight day (2026-11-01) goes
with b01.

**Cut line:** b01 to b12 cover 2025-11 to 2026-10, twelve complete months and
all four seasons. If collection is interrupted, these months matter most.

Scaled from the measured pilot day, one month is about 45 minutes of query
time and 2.1 GB of Parquet. The two-year set is about 18 hours of query time
and 52 GB. The calendar time depends on how often you log in. Two to four
weeks is realistic.

## Gate per batch

A batch moves on only when each step passes:

1. `run` finished with no pending hours or flight days. Only `source_gap`
   states and gap flags remain as exceptions.
2. `validate` passed with no unexplained anomalies.
3. `reconcile` matched the source on the sampled hours.
4. `report` written and reviewed.
5. `accept` recorded.
6. `publish` (verified backup to `E:`).

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

- Dataset summary for both datasets: expected, complete, empty, `source_gap`
  and failed hours or days, totals for rows and bytes, unique aircraft,
  per-month table.
- Restore test: recover a month from the `E:` backup and compare hashes.
- Record the processing-epoch split and the known gaps in the summary.

## After the window

Later extensions are separate decisions:

- Incremental collection for hours older than 48 h, which fits a scheduled job
  only if unattended OpenSky login is solved.
- A second airport or a larger region, as a new dataset.
