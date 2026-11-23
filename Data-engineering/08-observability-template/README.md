# E08 · Observability and DE platform template

**Status:** planned · [Roadmap](../README.md) · [Delivery plan](../docs/delivery-plan.md)

Close the DataOps loop by turning dbt run artifacts into operational observability metrics and extracting a reusable Data Engineering project template validated against a second data source.

## Deliverables

- Artifact parser ingesting dbt `run_results.json` and `sources.json` into operational audit tables (`ops_dbt_run_audit`, `ops_freshness_slo`) tracking model durations, test failure rates, freshness lag, and BigQuery `bytes_billed`.
- Extracted Data Engineering template (package skeleton, `dbt` starter structure, SQLFluff + Slim CI workflow, contract + test conventions) keeping domain contracts independent per workload.
- Second lightweight source/domain (e.g., ECB daily FX summary mart) onboarded through the template in the same repository without colliding with the charging commerce warehouse.

## Acceptance

1. An injected source delay triggers a recorded freshness SLO breach in `ops_freshness_slo` alongside the automated recovery check.
2. The second workload passes `sqlfluff`, `pytest`, and `dbt build` cleanly using the extracted template without modifying the primary charging commerce models.
3. Onboarding friction and measured template setup steps are recorded in the stage evidence.
