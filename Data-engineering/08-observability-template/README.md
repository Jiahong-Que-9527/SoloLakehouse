# E08 · Observability and DE platform template

**Status:** accepted 2026-11-24 — `audit-dbt` CLI + Airflow task (trigger_rule='all_done'): ops_dbt_run_audit / ops_freshness_slo idempotent by `invocation_id`; injected +71h staleness → BREACH row + alert JSON + exit 2; DE template extracted under `reference-warehouse/template/` and proven on the `examples/ecb_fx_mart` second workload (build 9/9, sqlfluff clean, zero edits to charging_commerce) · [Roadmap](../README.md) · [Design](docs/design.md) · [Implementation plan](docs/implementation.md) · [Delivery plan](../docs/delivery-plan.md) · [Evidence](evidence/e08-acceptance.md)

Close the DataOps loop by turning dbt run artifacts into operational observability metrics and extracting a reusable Data Engineering project template validated against a second data source.

## Deliverables

- Artifact parser ingesting dbt `run_results.json` and `sources.json` into operational audit tables (`ops_dbt_run_audit`, `ops_freshness_slo`) tracking model durations, test failure rates, freshness lag, and BigQuery `bytes_billed`.
- Extracted Data Engineering template (package skeleton, `dbt` starter structure, SQLFluff + Slim CI workflow, contract + test conventions) keeping domain contracts independent per workload.
- Second lightweight source/domain (e.g., ECB daily FX summary mart) onboarded through the template in the same repository without colliding with the charging commerce warehouse.

## Acceptance

1. An injected source delay triggers a recorded freshness SLO breach in `ops_freshness_slo` alongside the automated recovery check.
2. The second workload passes `sqlfluff`, `pytest`, and `dbt build` cleanly using the extracted template without modifying the primary charging commerce models.
3. Onboarding friction and measured template setup steps are recorded in the stage evidence.
