# Benchmark report

Collected on 2026-11-14. State vectors are `eddf_r75km` v1. Flights are
`eddf_flights` v1. Every day is under the review thresholds in the batch plan
(6 million rows, 100 MB of Parquet, 60 seconds per hour, 5 GB scanned per hour).

The client records one elapsed time, from the start of the query through the
last downloaded row. Query time and download time are that one measurement.
Null latitude and longitude are zero on every day: the query keeps only rows
with a position inside the box. No hour has a duplicate `(icao24, time)` key.

Peak memory is the maximum resident set of the collection process. The
2026-10-15 state-vector day was collected earlier, and that log did not record
it.

## State vectors

| Date | Rows | Parquet | Query + download | Max hour | Scan, max hour | Aircraft | Ground rows | Event time (UTC) | Peak memory |
|------|------|---------|------------------|----------|----------------|----------|-------------|------------------|-------------|
| 2024-11-15 | 3,224,635 | 60.3 MB | 89 s | 5.2 s | 0.97 GB | 1,832 | 749,699 | 1731628801–1731715199 | 728 MB |
| 2025-01-15 | 2,153,889 | 44.5 MB | 70 s | 4.8 s | 0.85 GB | 1,454 | 289,519 | 1736899200–1736985599 | 617 MB |
| 2025-07-15 | 3,507,597 | 72.2 MB | 93 s | 5.5 s | 1.07 GB | 2,349 | 457,755 | 1752537600–1752623999 | 699 MB |
| 2026-07-15 | 3,857,551 | 75.1 MB | 95 s | 6.2 s | 1.16 GB | 2,351 | 811,585 | 1784073600–1784159999 | 733 MB |
| 2026-10-15 | 3,640,281 | 70.7 MB | 90 s | 7.5 s | 1.15 GB | 2,296 | 720,509 | 1792022400–1792108799 | not recorded |

`2026-07-15` is the largest day. Scaled from that day, a 30-day month is about
2.3 GB and 48 minutes of query time, and the two-year set is about 55 GB and
19 hours of query time.

`2024-11-15T00` was the recovery test. The hour was published and then the
process stopped before the manifest. The resume moved that file to
`quarantine/`, collected the hour again, and committed it. The new file has
the same SHA256 as the quarantined file. A second run of the day skipped all
24 hours and left the manifests unchanged.

## Flights

| Date | Rows | Parquet | Query + download | Scan | Aircraft | Departures | Arrivals | firstseen–lastseen | Peak memory |
|------|------|---------|------------------|------|----------|------------|----------|--------------------|-------------|
| 2024-11-15 | 1,201 | 5.6 MB | 6.6 s | 0.59 GB | 454 | 607 | 600 | 1731571012–1731715196 | 652 MB |
| 2025-01-15 | 995 | 4.9 MB | 4.9 s | 0.53 GB | 412 | 492 | 510 | 1736836745–1736985262 | 558 MB |
| 2025-07-15 | 1,328 | 6.5 MB | 6.3 s | 0.69 GB | 479 | 664 | 666 | 1752453548–1752623967 | 697 MB |
| 2026-07-15 | 1,300 | 7.3 MB | 7.6 s | 0.81 GB | 479 | 644 | 658 | 1784010500–1784159841 | 773 MB |
| 2026-10-15 | 1,333 | 7.3 MB | 7.3 s | 0.78 GB | 487 | 664 | 675 | 1791955495–1792108789 | not recorded |

Departures plus arrivals are higher than the row count because some flights
have both estimated airports set to EDDF. Over 731 days this is about one
million flights and 5.4 GB.

The machine-readable copy is
`reports/benchmark/20261114-benchmark.json` under the data root.
