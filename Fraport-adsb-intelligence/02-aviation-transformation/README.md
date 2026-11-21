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
- **M3.** Data contract and Release Gate. Release `v001`, and a rejected
  release shown from a failing fixture. Done (2026-11-21). `v001` came from
  the 2026-07-01 gold output and `v002` from the pilot week, which closes
  the vertical slice V0 of the project plan.
- **M4.** Full dataset. Record run ID, source window, quality results and the
  outcome of a repeat run. In progress (2026-11-21, paused at 208/727
  Silver days — see "Full dataset run (M4, in progress)" below for the
  resume procedure).
- **M5.** Container image and CI. Optional engine comparison (DuckDB, Polars,
  Spark) on the same input. Done (2026-11-21, image builds and runs the
  synthetic suite in CI; the optional engine comparison is not planned).

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
(55.5%), 1,894 censored (`censored_few_points` — the ADS-B ground-coverage
limit), 174 no_surface, 2 no_airborne_approach, 3 surface_without_approach.
Output: `eddf-gold-ground-ops-pilotweek-20261121a`.

Recorded run (2026-07-01): 650 candidates -> 395 labeled (61%), 244
censored (surface points < 2 - the ADS-B ground-coverage limit), 9
no_surface, 2 no_airborne_approach. Labeled taxi-in: median 1.8 min, max
14.8 min, path up to 3,285 m; 169 flights carry a >30 s taxi gap.

## Full dataset run (M4, in progress)

**[GLM·2026-11-21]** Scope: the two-year window 2024-11-01 to 2026-10-31
(727 days, dataset `v1` as defined in the batch plan). The extension months
(2024-01 to 2024-10 collected so far, later b35-b60) ride a second pass
once acquisition finishes. Pipeline, chosen for the 30 GB RAM budget:

1. **Silver per day** (`full_run.sh silver`) — a single multi-month run
   would accumulate ~90M rows in Python and OOM; per-day peaks at ~3 GB,
   runs 2 workers in parallel, and is restartable at day granularity.
2. **Monthly merge** (`merge_silver_month.py`) — DuckDB streams a month of
   daily outputs into one root without Python-side accumulation.
3. **Gold per month** (`full_run.sh gold`) — deliberately not per day:
   taxi-in windows cross midnight, so a day-local gold run would lose
   boundary arrivals.
4. Monthly releases through the gate, then ingestion (03 M5).

**Status (paused 2026-11-21):** 208/727 days of Silver are complete
(through 2025-05), zero failures, all with verified manifests. Half-done
days are auto-redone: the driver counts a day as done only when its
`run_manifest.json` exists. To resume, run:

```bash
cd Fraport-adsb-intelligence/02-aviation-transformation
./full_run.sh silver   # continues from 2025-05-XX, skips the 208 done days
./full_run.sh gold     # after silver completes: monthly merge + gold
```

State lives in `/home/bill/slh-data/full-20241101-20261031/`
(`silver/`, `silver-monthly/`, `gold/`, `logs/`), outside the repository.
After both phases: one release per month (`v003-2024-11` … `v003-2026-10`)
through `release_gate.py`, repeat-run verification on one month, then
ingestion and the findings report in project 03 (its M5).

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
docker build -t eddf-transformation Fraport-adsb-intelligence/02-aviation-transformation
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
