# M02 · Feature pipeline and point-in-time contract

<!-- [魏征·2026-11-21] Initialize stage planning. -->

**Status:** accepted (2026-11-22) · [Roadmap](../README.md) · [Contract](../docs/feature-contract.md) · [Acceptance record](evidence/m02-acceptance.md)

Turn the availability table into code: point-in-time features that training and serving compute through one path, with leakage tests that fail loudly.

## Deliverables

- The `features` package implementing the contract's families: calendar, station attributes, demand lags and rolling windows, forecast-joined weather, tariff and events.
- Materialization to Parquet with a feature manifest (schema version, source data release ID, checksums) and a loader that enforces `available_at <= issue time`.
- The leakage test suite from the contract: shift test, forecast-reference test and duplicate-materialization test.
- Contract upkeep: every family added at this stage is written into the [feature contract](../docs/feature-contract.md) tables.

## Acceptance

1. Shifting every `available_at` backward makes the loader reject the affected rows; the shift test fails if the loader is bypassed.
2. Two materializations from the same data release ID produce byte-identical Parquet and manifests.
3. A training split built for issue date T contains no row with `available_at > T`, verified by an automated check over every fold.

M03 consumes feature releases; the evaluation harness must be able to rebuild features for any historical issue date.
