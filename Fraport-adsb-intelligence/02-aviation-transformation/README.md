# 02 · Aviation Transformation

**Runtime:** Local machine (WSL Ubuntu). Python and DuckDB, driven by a CLI.

Read the Bronze dataset from project 01 and build the Silver and Gold layers
locally. Publish Gold through a Release Gate. See
[ADR-003](../docs/adr/ADR-003-local-bronze-silver-published-gold.md).

## Why local

The data is about 55 GB of Parquet, scaled from the busiest benchmark day, 2026-07-15.
DuckDB processes that on one machine. The raw data stays under local control,
and nothing in this subproject needs a cluster. The code is containerised and
tested in CI so the same logic runs anywhere.

## Scope

**[房玄龄·2026-11-21]** The Silver layer is re-planned as a neutral
observation layer (see
[ADR-006](../docs/adr/ADR-006-neutral-silver-observation-layer.md)): it
records what was observed, for every aircraft, for the full day and
region, with no business semantics. Arrival threading, taxi usability
flags and labels move to Gold use-case markets, starting with
`gold/ground_ops`. The Bronze `onground` flag is carried but never trusted
(the `3c618b` case on 2026-07-01 shows it all-airborne while real ground
movement is observable).

- **Silver v2.** Four tables from full-day full-region Bronze reads:
  `observations` (every fresh position update, airborne and ground),
  `segments` (per-aircraft continuous runs with documented break
  reasons), `flights` (deduplicated flight records), and `daily_coverage`
  (per-aircraft and daily trust statistics). Every rule that removes or
  repairs a row is recorded.
- **Quality.** A report per run: completeness, segment and gap statistics,
  coverage distributions. `daily_coverage` is the factual basis for any
  downstream coverage claim.
- **Gold markets.** Use-case-specific feature sets built on Silver. The
  first market, `gold/ground_ops`, carries the arrival threading, taxi-in
  features and labels, hourly traffic statistics and the training
  dataset, with a label coverage report.
- **Release Gate.** Export a Gold market under a data contract, with a
  field policy, checks, manifest, checksums and release ID. Block a
  release that fails a check. See the release layout in ADR-003.
- **Reference data.** Airport geometry from open data, with its source and
  version recorded.
- **Synthetic data.** A generator that produces data in the same schema, so
  the whole flow runs without real data.

## Layers

```text
Bronze   raw OpenSky state vectors and flights (from project 01)
Silver   neutral observations, segments, flights, daily coverage
Gold     use-case markets (ground_ops first), one per analysis family
Release  versioned Gold folder with manifest, contract and checks
```

## Milestones

- **M1'.** Silver v2 for one day with tests, on the pilot-week data. The
  2026-11-19 arrival-anchored M1 outputs remain local research drafts
  (ADR-006).
- **M2.** `gold/ground_ops`: taxi-in features and labels for the pilot
  week, with a coverage report.
- **M3.** Data contract and Release Gate. Release `v001` from the pilot week,
  and a rejected release shown from a failing fixture.
- **M4.** Full dataset. Record run ID, source window, quality results and the
  outcome of a repeat run.
- **M5.** Container image and CI. Optional engine comparison (DuckDB, Polars,
  Spark) on the same input.

## Acceptance

- A repeat run on the same input and code revision gives the same output.
- Quality checks fail the run visibly, and the failure has a documented rerun
  procedure.
- A release is immutable. `_SUCCESS` is written last, after every file is
  verified against the manifest.
- A release that fails the contract is blocked and the reason is recorded.
- Gold carries per-flight features and reports label coverage.

## Depends on

Project 01 Bronze dataset. The pilot week is enough for M1 to M3.

## Outputs

Silver and Gold datasets, quality reports, run records and Gold releases for
projects 03 to 05.

## Silver v2 local build (M1')

**[GLM·2026-11-21]** Implemented per ADR-006. `silver_v2.py` reads the full
day (all 24 Bronze hour manifests), keeps every fresh position update —
airborne and ground — with the raw `onground` flag carried but unused, and
emits the four neutral tables plus `quality_report.md` and
`run_manifest.json`. The implausible-displacement break heuristic applies
only to surface pairs; airborne trajectories split on time gaps and source
partition issues alone.

```bash
uv run --locked python silver_v2.py \
  --bronze-root /path/to/local/aviation \
  --date 2026-07-01 \
  --output /path/to/new/local-output
```

Recorded run (2026-07-01, verified Bronze, zero unavailable hours):
2,278 aircraft, 3,209,592 observations, 10,269 segments (breaks: 5,832
`time_gap`, 2,159 surface `implausible_displacement`), 1,294 flight
records, cleaning dropped 728,116 stale states. The motivating case
`3c618b` now carries 5,134 points (2,345 airborne + 2,789 ground, 28
segments) in one stream, where the arrival-anchored M1 draft kept only its
225 ground points.

## Silver M1 local pilot

**[GLM·2026-11-21] Superseded as the target design by ADR-006 (neutral
Silver v2). The commands and tables below remain valid as the recorded
research drafts: the arrival-anchored logic moves to `gold/ground_ops`.**

**[房玄龄·2026-11-19]** The M1 CLI covers the 2026-07-01, 2026-09-01, and
2026-10-01 UTC arrival cohorts. It verifies the committed Bronze manifest
and checksum for each input partition. Adjacent UTC hours are read only
when a candidate window crosses midnight. OpenStreetMap geometry is read from
the local pilot snapshot supplied as `--geometry-dir` (`geometry-*.osm`).

Run from this directory with Python 3.13 and uv:

```bash
uv sync --locked --python 3.13
uv run --locked python silver_m1.py \
  --bronze-root /path/to/local/aviation \
  --geometry-dir /path/to/local/osm-snapshot \
  --output /path/to/new/local-output
```

The output directory must be new and outside the repository and input
directories. Four Parquet tables join by `arrival_id` and `day_utc`:

- `arrival_coverage` has one row per deduplicated EDDF arrival candidate,
  including candidates with no usable ground points.
- `surface_points` contains fresh position updates, their airport vicinity
  flags, and their fragment and point numbers.
- `surface_fragments` describes uninterrupted sequences, including
  single observations. A path length of at least 30 m over consecutive
  observed points is flagged as observed movement.
- `surface_breaks` links neighboring fragments and records the reason
  the line was split: a source partition issue, a fresh airborne observation,
  a gap above 30 seconds, or an implausible displacement.

Time columns ending in `epoch_s` are Unix seconds in UTC. The first fresh
ground position near a runway with a preceding fresh airborne position is
an arrival anchor hint. Without that hint the analysis looks for ground points
from two minutes before the candidate timestamp. The ground search is bounded
to 40 minutes from the analysis start and may stop earlier at subsequent
airborne activity. Position freshness is based on `lastposupdate`; the
pipeline does not bridge gaps or infer gate arrival. A station-adjacent point
only means proximity to a mapped stand. Fragment spans are observation spans.

`quality_report.md` includes coverage and break counts. `run_manifest.json`
records source, geometry, code and output fingerprints. To verify a repeat,
run the same command with a second new output path and compare the manifests.
Both output directories contain local research data.

### Date-scoped dual-flow pilot

**[房玄龄·2026-11-19]** The default date set remains the original three-day
baseline. Pass `--date YYYY-MM-DD` for one UTC day or pass a text file with
one day per line via `--date-list`. For independent day-level reruns, give
each single-day execution a new output directory.

The crossing study consumes one verified arrival Silver day and its
corresponding Bronze flight and state-vector manifests:

```bash
uv run --locked python crossing_observations.py \
  --date 2026-07-01 \
  --bronze-root /path/to/local/aviation \
  --geometry-dir /path/to/local/osm-snapshot \
  --arrival-silver /path/to/one-day-silver-output \
  --output /path/to/new/local-crossing-output
```

It writes three Parquet tables: arrival event evidence, departure occupancy
evidence (including unresolved candidates), and observed 25C departure
positions and gaps. An airborne runway-axis inference does not establish
ground occupancy. A time with no overlap in the observed source remains
unverified as runway vacancy.

The default M8/L5 and holding geometry are provisional. An optional local
`--crossing-config` JSON can supply `south_connector`, `north_connector`,
`holding_point_xy_m` (east/north offsets in metres using the module's EDDF
origin and scale), and `geometry_status`. Record the AIP source and effective
date in the config when verified. The run manifest records the geometry
status and input hashes. Keep real data and outputs outside Git.
