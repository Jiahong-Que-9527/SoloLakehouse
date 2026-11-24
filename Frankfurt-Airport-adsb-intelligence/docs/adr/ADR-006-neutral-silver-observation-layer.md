# ADR-006: Neutral Silver observation layer

**Status:** Accepted.

## Context

The current Silver M1 build is anchored on the taxi-in use case of
subproject 05: it reads only the arrival candidate window (-420 s to
+3000 s around an anchor), keeps only points in the airport vicinity, keys
every table by `arrival_id`, and carries a `publishable_as_taxi_in` flag.
That couples the cleaned observation layer to one business question.

Real data shows what this costs. For icao24 `3c618b` on 2026-07-01:

- Bronze holds 1392 observations for the turnaround window at roughly 1 Hz
  - a dense airborne approach, usable for far more than taxi analysis.
- The current Silver kept only the 225 ground points (32.5 min, 15
  fragments, 14 time-gap breaks). The airborne descent was dropped at the
  Silver boundary, so no consumer can reconstruct the approach-land-taxi
  line from Silver alone.
- The Bronze `onground` flag is unreliable: all 1392 states are flagged
  airborne while the geometry-plus-freshness analysis finds real ground
  movement. Any phase annotation must therefore be derived from geometry,
  altitude and velocity, never from the flag.

A future analysis that is not about ground operations (throughput, runway
configuration, approach studies, delay attribution) would need a second
pass over Bronze, which is the most expensive read in the pipeline.

## Decision

Silver becomes a neutral observation layer. Its contract is: "what was
observed this day in this region, and how trustworthy is it" - it answers
no business question on its own. Use-case semantics move to Gold markets.

Silver v2 has four tables, partitioned by `day_utc`, built from full-day
full-region Bronze reads:

| Table | Grain | Key columns |
|---|---|---|
| `observations` | each fresh position update (airborne and ground) | icao24, serial, time/lastposupdate/age, lat/lon, baro/geo altitude, velocity/heading/vertrate, source flags, generic geometry (airport reference distance, inside-polygon flag) |
| `segments` | per-aircraft continuous observation run, split on time gaps | icao24, segment_no, first/last time, point count, path length, max internal gap, break reasons (source partition issue, gap, implausible displacement) |
| `flights` | each deduplicated flight record | icao24, callsign, firstseen/lastseen, origin/destination, estimated times |
| `daily_coverage` | per aircraft per day, plus a daily rollup | observation count, first/last seen, gap statistics, update rate, inside-polygon share |

Rules:

- Phase annotation (air/ground/transition), arrival threading,
  `publishable_as_taxi_in`, anchors and labels are Gold logic. The first
  Gold market is `ground_ops`; it inherits the current M1 logic.
- No table is keyed by `arrival_id` at Silver level.
- The `onground` flag is carried as a raw column but never used for
  decisions.
- Gap handling stays honest: gaps are recorded, never bridged; gate
  positions are never inferred.
- The implausible-displacement break heuristic (>120 m at >105 m/s) is a
  surface-movement rule and applies only when both endpoints carry the raw
  ground flag; airborne trajectories split on time gaps and source
  partition issues alone.

## Consequences

- The M1 outputs (three-day baseline, full two-year run) are demoted to
  research drafts. They were never published through the Release Gate, so
  no contract breaks; `silver-eddf-m1-v1` is superseded by a v2 schema.
- The Silver build reuses the proven M1 pieces (manifest and checksum
  verification, freshness filter, gap segmentation, break reasons, geometry
  loading) but drops the arrival-candidate driver and the airport-window
  read.
- Per-day Silver storage and compute grow because all observations are
  kept; the Bronze read, the most expensive step, is paid once for every
  future use case.
- The Release Gate design (ADR-003) is unchanged: releases still carry
  manifest, contract, checks and a last-written `_SUCCESS`. Consumers 03,
  04 and 05 keep their consumption pattern; Gold markets are simply the
  unit of release content.
- The crossing study keeps consuming Silver plus its own use-case logic,
  now from the neutral layer.
- M2 is redefined as `gold/ground_ops` (arrival threading, taxi features
  and labels, label coverage report) instead of a Silver-shaped Gold.

## Revisit when

- Full-day observation storage becomes a cost or volume problem; then a
  documented region prefilter may become a Silver-wide rule.
- A use case needs a different segmentation (for example airborne-only
  sampling or a coarser grid); segment logic may grow a variant rather
  than a second layer.
- The `onground` flag quality is re-evaluated on later OpenSky epochs.
