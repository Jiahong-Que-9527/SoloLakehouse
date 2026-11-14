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
(about 52 GB, scaled from the 2026-10-15 pilot day).

OpenSky limits queries to 100 GB scan, two concurrent queries and 30 minutes
each. Its OAuth session expires after a few days.

## Decision

- Collect a new dataset `eddf_r75km` v1: a rectangle about 75 km around EDDF,
  for `[2024-11-01, 2026-11-01)` UTC.
- Store it on the WSL ext4 disk in Hive-partitioned Parquet with ZSTD and an
  explicit schema. Keep the legacy dataset unchanged.
- Collect hour by hour and deliver in 24 monthly batches. Each batch is
  validated, reconciled, reported and accepted before the next is published.
- Use hour manifests as the commit record and SQLite as a rebuildable index.
- Also collect `flights_data4` for EDDF arrivals and departures as dataset
  `eddf_flights` v1, one file per source day, so Silver has flight-level
  context.
- Run discovery, a seven-day pilot and five benchmark days first. Measure
  volume, query time and scan, and check the results against the legacy
  receipts.
- Decide whether to keep the `serials` column with an A/B test in the pilot,
  before the monthly batches.
- Account for hours inside documented OpenSky gaps with an explicit
  `source_gap` state.
- Order batches so that twelve complete months finish first, in case the
  collection is interrupted.
- Keep Bronze as source columns with no cleaning. Flag documented OpenSky
  gaps and processing changes instead of altering data.
- Back up to `/mnt/e` after each accepted batch. Bronze is not uploaded to
  the cloud (ADR-003).

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
- The schedule is tight, so the most valuable months run first.
- `flights_data4` shows inferred airports and times. It does not replace
  airport ground truth.

## Revisit when

- The pilot crosses a review threshold.
- OpenSky limits or access change during collection.
- A use case needs `serials`, a wider region or another airport.
