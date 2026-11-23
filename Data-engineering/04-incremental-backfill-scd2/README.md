# E04 · Incremental models, backfill and SCD Type 2

**Status:** implemented (acceptance evidence recorded, pending owner review) · [Roadmap](../README.md) · [Design](docs/design.md) · [Implementation plan](docs/implementation.md) · [Delivery plan](../docs/delivery-plan.md) · [Data contract](../docs/data-contract.md) · [Evidence](evidence/e04-acceptance.md)

Handle late-arriving settlements, deterministic window backfills, and slowly changing station/tariff attributes without rewriting full history or corrupting historical facts.

## Deliverables

- `fct_charging_sessions` converted to `materialized='incremental'` (`merge` strategy, `unique_key='session_id'`) with a 48-hour lookback window and `--vars` support for bounded date-range backfills.
- `dbt snapshot` definitions (`dim_stations_scd2`, `dim_tariffs_scd2`) tracking station kW upgrades, operator transfers, and tariff regime changes across `t0/t1/t2` snapshots.
- Point-in-time interval join linking each charging session to the station and tariff version valid at `session_started_at`.

## Acceptance

1. Injecting a 48-hour late settlement batch and re-running the incremental build updates/inserts the late rows with zero duplicate `session_id` keys.
2. Row-by-row comparison proves incremental + backfill output matches `dbt build --full-refresh` identically.
3. Historical sessions retain the `dim_tariffs_scd2` price effective at `session_started_at` even after a newer tariff snapshot is applied.
