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
- **M2.** `gold/ground_ops`: taxi-in proxy labels and descriptive fields for
  the pilot week, with a coverage report. Project 04 builds predictive
  features from local observations at the prediction cutoff.
- **M3.** Data contract and Release Gate. Release `v001`, and a rejected
  release shown from a failing fixture. Done (2026-11-21). `v001` came from
  the 2026-07-01 gold output and `v002` from the pilot week, which closes
  the vertical slice V0 of the project plan.
- **M4.** Full dataset. The two-year Geometry v2 backfill verified 730
  Silver dates and 24 monthly releases. See [the backfill handoff](#backfill-status-and-handoff)
  and [BigQuery reconciliation](../03-airport-analytics/README.md#geometry-v2-handoff-m5).
- **M5.** Container image and CI. Done (2026-11-21). The image builds and
  runs the synthetic suite in CI.

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

## Gold ground_ops (M2)

**[GLM·2026-11-21]** `gold_ground_ops.py` consumes only the Silver v2
tables. Candidate arrivals come from the Silver flights table
(`estarrivalairport = EDDF`, EDDF->EDDF turnaround phantoms excluded); the
touchdown estimate is the last airborne observation before the first
surface observation (geoaltitude present -> null within 15 km) in a
+-30 min window around the flight's `lastseen`, which real data shows
approximates touchdown. The taxi-in label runs from the first surface
point (within 5 km) to the last point within 1 km, capped at 45 min. Every
candidate carries a coverage status; stands are never inferred and gaps
are never bridged.

```bash
uv run --locked python gold_ground_ops.py \
  --silver-root /path/to/silver-v2-output \
  --date 2026-07-01 \
  --output /path/to/new/local-output
```

`--date-list` (one ISO date per line) selects several days in one run —
that is how the pilot week was built. The flag previously parsed but
ignored its input; fixed on 2026-11-21.

Recorded pilot-week run (2026-10-12 to 2026-10-18, from
`eddf-silver-v2-pilotweek-20261121a`): 4,656 candidates, 2,583 labeled
(55.5%), 1,894 censored with fewer than two points qualifying under the
1 km rule, 174 no_surface, 2 no_airborne_approach, 3 surface_without_approach.
Output: `eddf-gold-ground-ops-pilotweek-20261121a`.

Recorded run (2026-07-01): 650 candidates -> 395 labeled (61%), 244
censored with fewer than two qualifying points under the 1 km rule, 9
no_surface, 2 no_airborne_approach. Labeled taxi-in: median 1.8 min, max
14.8 min, path up to 3,285 m; 169 flights carry a >30 s taxi gap.

## Full dataset run (M4, in progress)

**[GLM·2026-11-21]** Scope: the two-year window 2024-11-01 to 2026-10-31
(730 calendar days, dataset `v1` as defined in the batch plan). The extension months
(2024-01 to 2024-10 collected so far, later b35-b60) ride a second pass
once acquisition finishes. Pipeline, chosen for the 30 GB RAM budget:

1. **Silver per day** (`full_run.sh silver`) — a single multi-month run
   would accumulate ~90M rows in Python and OOM; per-day peaks at ~3 GB,
   runs 2 workers in parallel, and is restartable at day granularity.
2. **Monthly merge** (`merge_silver_month.py`) — DuckDB streams completed
   daily outputs into one root. The monthly `run_manifest.json` records
   included and missing dates. Missing days are skipped without triggering a
   daily run. A month with no completed days writes its manifest and skips Gold.
3. **Gold per month** (`full_run.sh gold`) — each flight stays with its
   original Silver date. Its observation window can cross UTC midnight.
   When the window reaches outside the month, Gold reads observations from
   the relevant daily Silver folders and records unavailable dates. Release
   manifests retain the date coverage and observation gaps.
4. Monthly releases through the matching label contract, then ingestion (03 M5).

### Backfill status and handoff

**Checkpoint (2026-11-22, 22:34 CET):** 636 of 730 Silver dates and 13 of
24 Geometry v2 monthly packages were complete. The February 21, 2026 run
was recovered after fixing coverage statistics for aircraft whose
positions were all stale. Bronze manifests were present for all 730 days
and their hourly partitions.

The active run is under
`/home/bill/slh-data/full-20241101-20261031-geometry-v2`. Its local
supervisor resumes unfinished phases and verifies the series. Check
`logs/driver-silver.log`, `logs/driver-ready-months.log`,
`logs/driver-gold-release.log`, and `logs/supervisor.log` before starting
a recovery run. The local completion evidence is `local-verification.json`
with 24 verified releases, each month's row count, and its Silver and
observation coverage. Use [the cloud pilot checklist](../03-airport-analytics/README.md#geometry-v2-handoff-m5)
after local verification.

If the supervisor has exited before completion, resume against the same
run directory and geometry snapshot:

```bash
cd Frankfurt-Airport-adsb-intelligence/02-aviation-transformation
export PARENT=/home/bill/slh-data/full-20241101-20261031-geometry-v2
export GEOMETRY_DIR=/path/to/local/osm-snapshot
./full_run.sh silver
./full_run.sh gold
APPROVER="..." ./full_run.sh release
```

Keep boundary-day Silver under `silver/` when available so edge flights
can use those observations without adding those dates to a release.
With `GEOMETRY_DIR` set, the driver uses `gold-geometry-v2/` and
`releases-geometry-v2/` under `PARENT`. It skips completed outputs and
retains the validation record for a blocked release.
Each monthly release passes through `release_gate.py` before ingestion
and the findings report in project 03 (its M5). Use a single label version
for the monthly series.

**November 2024 radius v1 verification (2026-11-22).** All 30 Silver dates
were available. Gold produced 17,051 candidates and 7,912 labeled rows
(46.4%). A repeat produced identical Gold data, report and manifest.
The release check blocked `v003-2024-11` at the 50% label-coverage
minimum. Synthetic tests verify observation windows that cross UTC
midnight and month end.

### Taxi-in coverage investigation

In November 2024, 6,723 of the 6,728 `censored_few_points` arrivals had
zero qualifying points within 1 km. A deterministic sample took four
arrivals per day from the censored pool with at least two distinct
surface position updates in the existing time window. All 120 sampled
arrivals had an observation beyond 1 km within 30 m of a mapped taxiway
or inside a mapped apron, and more than 30 m from the runway centreline.
61 showed at least 30 m of movement between sequential distinct updates
no more than 30 s apart on those surfaces.

To build Geometry v2, pass `--geometry-dir /path/to/local/osm-snapshot`
to `gold_ground_ops.py` with a fresh output directory. It admits observations
beyond 1 km when they meet the mapped-surface criteria, within the existing
5 km and time windows. It counts each position update once and records the
snapshot checksums and matching tolerances in the Gold manifest. The
geometry rule is opt-in. The comparison uses the local November 2026 OSM
snapshot as reference evidence for historical observations.

| Silver month | Arrival candidates | 1 km coverage | Geometry coverage | Median change on arrivals labeled by both |
|---------------|-------------------:|--------------:|------------------:|-------------------------------------------:|
| 2024-11 | 17,051 | 46.4% | 78.7% | +185 s |
| 2025-01 | 15,033 | 52.9% | 87.1% | +168 s |
| 2025-03 | 17,265 | 53.1% | 97.0% | +212 s |

The geometry outputs passed the existing contract checks locally, and
the November repeat produced identical arrivals and coverage report.
These are proxy labels. The paired difference quantifies a change to
the metric, so a geometry release should identify its label definition
when compared with the 1 km releases.

### Taxi-in label versions

| Label version | Gold invocation | Release contract |
|---------------|-----------------|------------------|
| `taxi-in-radius-v1` | Default Gold invocation | [ground_ops.yaml](contracts/ground_ops.yaml), version 1 |
| `taxi-in-geometry-v2` | Gold with `--geometry-dir` | [ground_ops_geometry.yaml](contracts/ground_ops_geometry.yaml), version 2 |

Both versions use the same Gold columns. The release gate validates the
label version and copies it into the release manifest. It treats historical
radius manifests without a version field as v1. Geometry v2 requires an
explicit version and snapshot checksums. Rebuild experimental geometry
outputs with the current Gold command before packaging.

Local acceptance also covered the 2026-10-12 to 2026-10-18 pilot week.
Geometry v2 labeled 4,405 of 4,656 arrivals (94.6%), compared with
2,583 (55.5%) in the original radius release.

```bash
uv run --locked python release_gate.py \
  --gold-root /path/to/monthly-geometry-gold \
  --contract contracts/ground_ops_geometry.yaml \
  --output /path/to/new/local-release \
  --release-id geometry-v2-2024-11 --approver "..."
```

## Release Gate (M3)

**[GLM·2026-11-21]** `release_gate.py` packages one gold market output as an
immutable, versioned release per ADR-003: `data/`, `manifest.json`,
`contract.yaml`, `validation.json`, `approval.json`, and a `_SUCCESS` written
last after every file is re-verified against the manifest. The gate first
re-checksums the gold input against its own `run_manifest.json` (including the
`input_id` recomputation) and refuses a mismatched or tampered input before it
stages anything. Thresholds live in
[contracts/ground_ops.yaml](contracts/ground_ops.yaml), never in code; the
owner field-policy decision (2026-11-21) keeps `icao24` and `callsign` in the
release, with the rationale recorded in the contract.

```bash
uv run --locked python release_gate.py \
  --gold-root /path/to/gold-output \
  --contract contracts/ground_ops.yaml \
  --output /path/to/new/local-release \
  --release-id v001 --approver "Jiahong Que" --notes "..."
```

Recorded release `v001` (2026-11-21, from the 2026-07-01 gold output
`eddf-gold-ground-ops-20260701-164048`, source commit `86d0a7e`): 650 rows,
all seven checks passed — schema (15 columns), grain uniqueness (0
duplicates), label coverage (395/650 = 0.608 against a 0.5 floor),
taxi-in range, checksums, row count. Output:
`eddf-release-ground-ops-v001-20261121a`.

Recorded release `v002` (2026-11-21, from the pilot-week gold output
`eddf-gold-ground-ops-pilotweek-20261121a`): 4,656 candidate arrivals over
2026-10-12 to 2026-10-18, all seven checks passed — label coverage
2,583/4,656 = 0.555. This closes the vertical slice V0: pilot week through
Silver v2, Gold, release gate and a governed release. Output:
`eddf-release-ground-ops-v002-20261121a`.

Blocked demonstration: a fixture with 300 labeled rows demoted to
`no_surface` (coverage 0.146) fails `label_coverage`; the gate exits
non-zero, writes `validation.json` with `status: blocked`, and leaves no
`_SUCCESS` and no `approval.json`.

### Container image (M5)

The image carries the code, the contract and the synthetic suite — never
data. The default command runs the suite as a smoke test:

```bash
docker build -t eddf-transformation Frankfurt-Airport-adsb-intelligence/02-aviation-transformation
docker run --rm eddf-transformation
```

CI builds the image and runs that suite on every pull request that touches
this directory. Run a tool against local data by mounting the data root and
overriding the entrypoint.

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

Recorded pilot-week run (2026-10-12 to 2026-10-18 UTC, seven days in one
run, verified Bronze, zero unavailable hours): 15,346 aircraft-days,
20,918,106 observations, 59,264 segments, 9,312 flight records. Output:
`eddf-silver-v2-pilotweek-20261121a`.

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
