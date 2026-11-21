# M01 · Problem framing and data foundation

<!-- [魏征·2026-11-21] Initialize stage planning. -->

**Status:** planned · [Roadmap](../README.md) · [Evidence guide](../docs/evidence-guide.md)

Freeze what the model predicts and when, then build the seeded synthetic world it learns from — including the validation that keeps later stages honest.

## Deliverables

- The task contract: target definition, issue time, horizon, and the issue-time availability table (moved from draft to v1 in the [feature contract](../docs/feature-contract.md)).
- The seeded generator implementing the domain and regimes in the [workload README](../reference-workload/README.md), with a config file per dataset release.
- A dataset validation suite: schema, ranges, per-station continuity and regime invariants (the tariff step lands on the announced date; new stations have no earlier rows).
- The first dataset release: versioned Parquet folder with manifest, checksums and release ID, mirroring the ADR-003 pattern.
- An EDA report committing the headline distributions and seasonality checks that M03 baselines will assume.

## Acceptance

1. The same seed and config regenerate the dataset with identical SHA-256 for every partition.
2. The validation suite fails on each seeded corruption case (mutated tariff date, shifted forecast reference time, dropped station-hours) and passes on the clean release.
3. The release manifest lists every partition checksum, and the EDA report cites the release ID it describes.

M02 consumes the release ID; later stages must never silently regenerate data with a different seed.

## How to start

1. Resolve the M01 decisions in the [delivery plan](../docs/delivery-plan.md) — availability table freeze, station and tariff schema, regime schedule, release layout — and record them with dates.
2. Scaffold the `reference-workload` package (`pyproject.toml`, uv lock, pytest and Ruff config) following the repository's established project conventions.
3. Implement `charging_forecast.contract` (schemas and the availability table) and `charging_forecast.generator` with the seeded regimes, then the validation suite.
4. Produce the first dataset release with its manifest, and the EDA report.
5. Run the three acceptance checks and record the evidence per the [evidence guide](../docs/evidence-guide.md).

The stage is complete when its status reads accepted with evidence links, not when the code merely runs.
