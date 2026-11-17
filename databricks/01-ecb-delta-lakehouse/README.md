# ECB Delta Lakehouse

<!-- [房玄龄·2026-11-15] Define the D01 to D04 project brief. -->
<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

**D01 · Planned** · [Databricks roadmap](../README.md) · [Design](docs/design.md) · [Implementation plan](docs/implementation.md)

Model ECB reference exchange rates and policy rates in Delta. Begin with a fixed quarter of the daily USD/EUR series, then add one policy-rate series with its
own publication calendar and units.

## Technical scope

PySpark, Delta Lake, SQL and Bronze, Silver and Gold models.

## Input and output

- **Input.** Fixed ECB extracts and small fixtures. Record the source series keys, observation dates, units and source windows.
- **Output.** Bronze source batches, normalized Silver observations keyed by series and date, and a versioned Gold release with derived metrics. D02 can package the transforms and D05 can consume a specific Delta snapshot.

## Acceptance

1. Verify known output rows and metric values, then rerun the same inputs and check key uniqueness.
2. Apply a controlled update with Delta MERGE and inspect the pre-update and post-update versions.
3. Trace a Gold release to the input batch, table version, quality-check result and source commit.

[ECB daily reference exchange-rate series](https://data.ecb.europa.eu/data/datasets/EXR/EXR.D.USD.EUR.SP00.A)

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->
