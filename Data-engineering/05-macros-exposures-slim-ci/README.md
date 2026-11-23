# E05 · Macros, exposures and Slim CI

**Status:** planned · [Roadmap](../README.md) · [Delivery plan](../docs/delivery-plan.md)

Productionize dbt engineering workflows with reusable cross-database macros, downstream consumer lineage via exposures, and state-aware Slim CI in GitHub Actions.

## Deliverables

- Cross-database Jinja macros (safe division, currency normalization, incremental lookback watermark, target-aware BigQuery partitioning helper) plus `dbt_utils` package integration.
- `exposures.yml` declaring downstream BI dashboard and ML feature consumers, plus static `dbt docs generate` lineage verification.
- Slim CI workflow in GitHub Actions comparing against a pinned production `manifest.json` (`dbt build --select state:modified+ --defer --state ...`).

## Acceptance

1. `dbt docs generate` builds complete lineage from `sources` through `exposures` with zero undocumented mart columns.
2. Modifying one downstream mart triggers Slim CI to build only the modified subgraph rather than the entire DAG, with model count and runtime recorded.
3. Modifying an upstream staging model correctly fans out through `state:modified+` to rebuild affected downstream marts and run their tests.
