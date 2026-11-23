# E07 · Orchestration with Apache Airflow

**Status:** planned · [Roadmap](../README.md) · [Delivery plan](../docs/delivery-plan.md)

Orchestrate the end-to-end warehouse pipeline (`ingest -> source freshness -> dbt snapshot -> dbt build -> revenue audit`) with **Apache Airflow** running locally in an isolated `uv` environment (plus an optional Docker Compose definition), and document failure recovery and orchestrator trade-offs.

## Deliverables

- Layered Airflow DAG (`charging_commerce_daily`) invoking the isolated `dbt` / ingestion CLI commands (or `astronomer-cosmos` TaskGroups) with logical execution dates (`{{ ds }}`) passed cleanly for idempotent backfills.
- Architecture Decision Record comparing **Apache Airflow** (this project) vs **Dagster** ([Mlops-engineering M08](../../Mlops-engineering/08-orchestration-dagster/README.md)) on asset lineage, backfill ergonomics, and operational footprint.
- Local runbook covering failed-task triage, downstream blocking, and single-task-group recovery.

## Acceptance

1. A full scheduled/backfilled DAG run succeeds locally from raw ingestion through BigQuery/DuckDB marts with recorded run IDs and task durations.
2. Injecting an upstream `source freshness` or dbt test failure halts downstream mart publication without leaving partial state.
3. Fixing the input and clearing only the failed Airflow task (`clear` / retry) completes the run idempotently without re-ingesting earlier clean partitions.
