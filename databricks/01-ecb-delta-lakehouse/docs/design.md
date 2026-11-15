# Design: ECB Delta Lakehouse

**D01 · Design only.** No application code in this directory yet.

Land ECB public series in Delta, clean them to one grain, and publish a versioned Gold table that a later job can rerun without duplicating observations. The project proves Bronze, Silver, Gold, MERGE, and time travel on a small fixed extract.

The source for this scope is the D01 section of the [subproject design note](../../../chatgpt-consulting-subprojects-design.md). The project [brief](../README.md) fixes the first series.

## 1. Decisions

| Topic | Decision |
|-------|----------|
| v1 series | Daily USD per EUR, `EXR.D.USD.EUR.SP00.A`, for one fixed quarter. Plus one policy-rate series with its own dates and unit. |
| Default input | Versioned sample files in this project. A live SDMX read is an optional adapter that writes the same Bronze schema. |
| Bronze | Append-only. One batch is one write, identified by `source_batch_id`. Rows are not cleaned here. |
| Silver | One row per `(series_key, observation_date)` after type checks and deduplication. Missing dates stay missing. |
| Gold | `daily_euro_indicators` for the series that exist. `monthly_financial_summary` is a view over Silver, not a second pipeline. |
| Policy rate on a daily grid | Gold may carry the last published policy rate forward and must label those rows `carried_forward`. Silver never fills gaps. |
| Incremental | `MERGE` on the Silver grain. A new date inserts. A corrected value for an existing date updates. An unchanged key is left in place. |
| History | Delta table history is the version record. A Gold release stores the Silver version it read. |
| Schema change | An added column bumps the contract. A type change creates a new table version. A silent overwrite is not allowed. |
| Tests | Transformation functions are tested locally. A workspace run is required only for the MERGE and time-travel evidence. |

## 2. Boundary

In scope: the two series, the three layers, MERGE, time travel, and SQL checks for the known sample rows.

Out of scope: job scheduling (D02), CDC (D03), Unity Catalog grants (D04), and model training (D05). This project writes tables in a schema the developer owns.

## 3. Architecture

```text
ECB sample files, or a later SDMX adapter
          |
          v
Bronze  bronze.raw_fx_rates, bronze.raw_ecb_rates
          |
          v
Silver  silver.clean_fx_rates, silver.clean_interest_rates
          |
          v
Gold    gold.daily_euro_indicators
        gold.monthly_financial_summary   view
```

Both Silver tables share the observation grain so a later series is another `series_key`, not another pipeline.

## 4. Contracts

Bronze columns, kept as received: `series_key`, `observation_date` (string), `value` (string), `unit`, `title`, `source_file`, `source_batch_id`, `ingested_at`.

Silver columns:

| Column | Meaning |
|--------|---------|
| `series_key` | ECB series key |
| `observation_date` | Date of the observation |
| `value` | Decimal in the source unit |
| `unit` | Source unit, unchanged |
| `frequency` | `daily` or `irregular` |
| `source_batch_id` | Batch that last wrote this key |

Silver rejects a row with a null key, an unparseable date, or a non-numeric value, and writes it to `silver.reject`. A duplicate key inside one batch keeps the last row in file order and counts the drop.

Gold `daily_euro_indicators` columns: `observation_date`, `usd_per_eur`, `policy_rate`, `policy_rate_status` (`observed` or `carried_forward`), `silver_version`, `release_id`.

The monthly view groups Gold by calendar month and reports the last FX fixing, the average FX, and the last policy rate. It does not invent a month the Silver range does not cover.

## 5. Behaviour

1. A full rerun of the same sample produces the same Silver keys and values. Delta version increases only when the MERGE changes a row. The acceptance query compares keys and values, not the version number.
2. Adding a later date merges that date only. Row counts of untouched dates stay equal.
3. A corrected value for an existing date is visible at the new version. `VERSION AS OF` the previous version still returns the old value.
4. The policy-rate series is not interpolated in Silver. Gold's carry-forward is computed in the Gold query and labelled.
5. A schema contract file lists column names and types. The job fails if the sample header does not match.

## 6. Delivery and cost

v1 runs as a Python job on a small warehouse or on local PySpark for the unit tests. No cluster is left running. The sample quarter is the whole input. Workspace evidence, when collected, names the table versions and the warehouse id.

## 7. Acceptance

1. Known sample rows match expected FX and policy-rate values. A second run does not add keys.
2. Apply one controlled correction with MERGE. Query the version before and the version after.
3. A Gold `release_id` traces to `source_batch_id`, the Silver Delta version, the reject count, and the git sha.

## 8. Handoff

D02 packages these transforms as tasks. D03 may reuse `(series_key, observation_date)` as a business key in a fixture. D05 reads a pinned `silver_version`. Each of those projects ships its own sample.
