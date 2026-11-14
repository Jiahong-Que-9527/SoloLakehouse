# 02 · Aviation Transformation

**Runtime:** Local machine (WSL Ubuntu). Python and DuckDB, driven by a CLI.

Read the Bronze dataset from project 01 and build the Silver and Gold layers
locally. Publish Gold through a Release Gate. See
[ADR-003](../docs/adr/ADR-003-local-bronze-silver-published-gold.md).

## Why local

The data is about 52 GB of Parquet, scaled from the 2026-10-15 pilot day.
DuckDB processes that on one machine. The raw data stays under local control,
and nothing in this subproject needs a cluster. The code is containerised and
tested in CI so the same logic runs anywhere.

## Scope

- **Silver.** Clean and type Bronze observations and record every rule that
  removes or repairs a row. Reconstruct per-aircraft trajectories with
  documented gap handling. Select the airport area (runways, taxiways and
  surroundings) from reference geometry. Identify arrival candidates and
  surface-movement events with documented thresholds.
- **Quality.** Run checks and write a report for each run: completeness,
  trajectory coverage and anomaly rates. Report how many flights have a usable
  ground track, because ADS-B ground coverage limits taxi-in times.
- **Gold.** Build flight-level taxi-in features and labels, hourly traffic
  statistics and the training dataset. Report label coverage.
- **Release Gate.** Export Gold under a data contract, with a field policy,
  checks, manifest, checksums and release ID. Block a release that fails a
  check. See the release layout in ADR-003.
- **Reference data.** Airport geometry from open data, with its source and
  version recorded.
- **Synthetic data.** A generator that produces data in the same schema, so
  the whole flow runs without real data.

## Layers

```text
Bronze   raw OpenSky state vectors and flights (from project 01)
Silver   clean observations, trajectories, arrival events
Gold     taxi-in features, hourly traffic, training dataset
Release  versioned Gold folder with manifest, contract and checks
```

## Milestones

- **M1.** Silver for one day with tests, on the pilot-week data.
- **M2.** Gold features and labels for the pilot week, with a coverage report.
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
