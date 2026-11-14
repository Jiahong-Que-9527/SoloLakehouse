# ADR-002: Regional dataset collected in monthly batches

**Status:** Proposed

## Context

The legacy fin dataset covers a 10 km by 10 km box around EDDF. It shows the
airport surface and only the last few kilometres of approach. The programme
needs approach, departure and surrounding traffic for arrival sequencing,
congestion features and trajectory work.

An OpenSky Trino query scans a whole hour partition, so its cost depends on
the number of hours queried far more than on the box size. A later change of
region means repeating every query. Parquet storage for two years is small
(about 31 GB estimated).

OpenSky limits queries to 100 GB scan, two concurrent queries and 30 minutes
each. Its OAuth session expires after a few days. Its terms restrict use to
non-profit research and education and require deletion when the research ends.

## Decision

- Collect a new dataset `eddf_r75km` v1: a rectangle about 75 km around EDDF,
  for `[2024-11-01, 2026-11-01)` UTC.
- Store it on the WSL ext4 disk in Hive-partitioned Parquet with ZSTD and an
  explicit schema. Keep the legacy dataset unchanged.
- Collect hour by hour and deliver in 24 monthly batches. Each batch is
  validated, reconciled, reported and accepted before the next is published.
- Use hour manifests as the commit record and SQLite as a rebuildable index.
- Run a seven-day pilot first. Measure volume, query time and scan, and check
  the results against the legacy receipts.
- Keep Bronze as source columns with no cleaning. Flag documented OpenSky
  gaps and processing changes instead of altering data.
- Back up to `/mnt/e` after each accepted batch. Upload to GCS only after
  OpenSky confirms that cloud storage is allowed.

## Rationale

- The scan cost is per hour, so a larger box is cheap and a second pass is
  expensive.
- Monthly batches match the length of one login session plus review, and make
  every unit of work resumable and auditable.
- Manifests as the commit marker make recovery simple after crashes.
- Source-column Bronze lets Silver choose its own cleaning rules.

## Consequences

- The estimates for rows, size and time are uncertain. The pilot gate can
  change the box, the period or the extraction rules.
- Two documented OpenSky gaps and one processing change fall inside the window
  and need flags in the data contract.
- Collection depends on manual logins every few days.
- Cloud upload and long-term retention depend on OpenSky's answer.

## Revisit when

- The pilot crosses a review threshold.
- OpenSky declines the two-year regional plan or cloud storage.
- A use case needs `serials`, a wider region or another airport.
