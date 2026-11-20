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

The 2026-10-12 to 2026-10-18 cross-check matched all 168 hours against the fin
receipts in `history-20261102-raw`: rows, distinct aircraft, minimum and
maximum event time, and ground rows. The compared box is latitude 49.98 to
50.07 and longitude 8.48 to 8.62. Report:
`reports/cross-check/20261114T223121Z-dde3.json`.

The recovery test used `2024-11-15T00`. The file was published and the process
stopped before the manifest. Resume quarantined that file, collected the hour
again, and committed it. The new file matches the quarantined SHA256. A second
run skipped all 24 hours of that day and did not change the manifests.

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

On 2026-07-15 the state vectors were collected again with `serials` and
compared with the v1 files. Row counts match on all 24 hours. Parquet grew
from 75.1 MB to 117.6 MB (1.57×). Query-plus-download grew from 95 s to 168 s
(1.76×). Peak memory was 1.08 GB. **v1 excludes `serials`.** The comparison
files are `reports/serials-ab/2026-07-15/`. A later version can add the column.

### Measurements and thresholds

| Measure | Earlier estimate | Measured 2026-10-15 | Busiest day, 2026-07-15 | Review threshold |
|---------|------------------|---------------------|-------------------------|------------------|
| Rows per day | 3.5 M | 3.64 M | 3.86 M | above 6 M |
| Parquet per day | 43 MB | 71 MB | 75 MB | above 100 MB |
| Query time per hour | 8 to 12 s | 1.7 to 7.5 s | up to 6.2 s | above 60 s |
| Scan per hour | about 0.7 GB | 0.53 to 1.15 GB | up to 1.16 GB | above 5 GB |
| Hours failed | 0 | 0 | 0 | any unexplained |

All five benchmark days are under every review threshold. The busiest is
`2026-07-15`: 3,857,551 rows, 75 MB of Parquet, 95 s of query time, 19.7 GB
scanned, 2,351 distinct aircraft, no duplicate keys. Null positions are absent
by construction. Scaled from that day, a 30-day month is about 2.3 GB and 48
minutes of query time, and the two-year set is about 55 GB and 19 hours of
query time. The day-by-day figures are in
[benchmark-report.md](benchmark-report.md).

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
time and 2.3 GB of Parquet. The two-year set is about 19 hours of query time
and 55 GB. The calendar time depends on how often you log in. Two to four
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

## Five-year extension

Decided on 2026-11-20. Not started. The collected window stays
`[2024-11-01, 2026-11-01)`. The extension moves the start to **2021-11-01**
and leaves the end where it is. That is five years, 1,826 days, 43,824 state
hours and 1,827 flight days (the existing extra flight day 2026-11-01 stays
on b01). New work is 1,096 days: **26,304 hours** and **1,096 flight days**,
in 36 monthly batches, **b25 through b60**.

Same dataset version. Bounds, columns and SQL do not change, so the files
stay on `eddf_r75km` v1 and `eddf_flights` v1. Do not recollect b01–b24. Do
not add `serials`. Do not upload Bronze.

### Before the first query

`run` rejects an hour outside `configs/dataset.eddf_r75km.v1.yaml`. Change
that file in the same session as b25, before collecting:

- `period.start` becomes `2021-11-01`. `period.end` stays `2026-11-01`.
  `flights.day_end` stays `2026-11-02`.
- Append b25–b60 to `configs/batches.yaml` using the calendar below.
- Update `test_batches_cover_the_dataset_period` to 60 batches, 43,824 hours
  and 1,827 flight days.

### Order and cut lines

Newest month first, so the first new month sits against the already checked
2024-11. One batch at a time. States, then flights, then the gate, then
backup. Do not start the next batch until the current one is published.

| Cut | Batches | Months | What is on disk if work stops here |
|-----|---------|--------|-------------------------------------|
| First year of the extension | b25–b36 | 2024-10 back to 2023-11 | Three years, Nov 2023 through Oct 2026, including a third winter |
| Second | b37–b48 | 2023-10 back to 2022-11 | Four years |
| Third | b49–b60 | 2022-10 back to 2021-11 | Five years, the full extension |

If a day has to be dropped, keep going only through the current cut. b25 is
the probe: it should look like 2024-11 (about 110,000 rows per complete hour,
same columns). A schema or column error on b25 stops the extension.

### Calendar

February 2024 has 29 days (696 hours). February 2022 and 2023 have 28 days
(672 hours). A 31-day month is 744 hours. A 30-day month is 720.

| Batch | Month | Hours | Documented gap hours |
|-------|-------|------:|---------------------:|
| b25 | 2024-10 | 744 | 0 |
| b26 | 2024-09 | 720 | 0 |
| b27 | 2024-08 | 744 | 0 |
| b28 | 2024-07 | 744 | 0 |
| b29 | 2024-06 | 720 | 0 |
| b30 | 2024-05 | 744 | 19 |
| b31 | 2024-04 | 720 | 0 |
| b32 | 2024-03 | 744 | 0 |
| b33 | 2024-02 | 696 | 0 |
| b34 | 2024-01 | 744 | 0 |
| b35 | 2023-12 | 744 | 67 |
| b36 | 2023-11 | 720 | 28 |
| b37 | 2023-10 | 744 | 0 |
| b38 | 2023-09 | 720 | 0 |
| b39 | 2023-08 | 744 | 0 |
| b40 | 2023-07 | 744 | 0 |
| b41 | 2023-06 | 720 | 9 |
| b42 | 2023-05 | 744 | 0 |
| b43 | 2023-04 | 720 | 0 |
| b44 | 2023-03 | 744 | 0 |
| b45 | 2023-02 | 672 | 0 |
| b46 | 2023-01 | 744 | 127 |
| b47 | 2022-12 | 744 | 0 |
| b48 | 2022-11 | 720 | 0 |
| b49 | 2022-10 | 744 | 0 |
| b50 | 2022-09 | 720 | 0 |
| b51 | 2022-08 | 744 | 0 |
| b52 | 2022-07 | 744 | 0 |
| b53 | 2022-06 | 720 | 0 |
| b54 | 2022-05 | 744 | 0 |
| b55 | 2022-04 | 720 | 0 |
| b56 | 2022-03 | 744 | 0 |
| b57 | 2022-02 | 672 | 0 |
| b58 | 2022-01 | 744 | 0 |
| b59 | 2021-12 | 744 | 0 |
| b60 | 2021-11 | 720 | 0 |

State command for a batch, with the month's UTC bounds. b25 is:

`run --from 2024-10-01T00:00:00Z --until 2024-11-01T00:00:00Z --max-duration 8h`

`collect-flights --from 2024-10-01 --until 2024-11-01 --max-duration 3h`

Then `validate --batch b25`, `report`, `accept`, `publish`. A `review`
outcome needs `--notes`. A `failed` outcome stops the gate.

### Gaps already on the list

OpenSky's published gap list, checked on 2026-11-20, has no gap before
2023-01. `known_gaps.yaml` already contains every published gap inside the
extension, plus the two observed 2026-05 hours from the first window. The
extension overlaps **250 hours** of published gaps. Those hours should commit
as `source_gap` when the global hour is empty. Do not add a gap because a
regional hour is `empty`.

The long gaps make whole flight days likely `source_gap` when the global day
partition is empty: **2023-01-19, 2023-01-20, 2023-01-21, 2023-01-22,
2023-12-03 and 2023-12-04**. b46 (2023-01) is the heavy one: 127 gap hours
across 2023-01-02T23–03T10 and 2023-01-18T11–23T07. That is an expected
result, not a failed batch.

`SOURCE_MISSING` still stops the range. Probe the global hour and its
neighbours before editing `known_gaps.yaml`. Add an hour only when the global
partition is empty, the neighbours exist, and the OpenSky page does not list
it.

### Pace, size and disk

Use the same pace as the second year: **two batches a day**, with about 15
minutes between `publish` and the next `run`. A third batch only when the
first two are published and someone is still present. At that pace the 36
batches take about **18 working days**. Login still dies mid-run; resume the
same `--from` and `--until`.

The finished two years are 51.6 GB and 12.53 TB scanned, with 20.7 hours of
query time. The same density for three more years is about **75 GB** of
Parquet, **19 TB** scanned and **31 hours** of query time. Older years may
be thinner. On 2026-11-20 the data disk had 857 GB free and `E:` had 317 GB
free, which holds this extension. Check both disks before each cut line.
Stop if `E:` has less than 120 GB free.

Stop a batch when a day exceeds 6 million rows, 100 MB of Parquet, 60 seconds
per hour, or 5 GB scanned per hour.

## After the window

Still separate decisions, after the five-year extension:

- Incremental collection for hours older than 48 h, which fits a scheduled job
  only if unattended OpenSky login is solved.
- A second airport or a larger region, as a new dataset.
