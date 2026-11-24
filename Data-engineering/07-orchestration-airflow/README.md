# E07 · Orchestration with Apache Airflow

**Status:** accepted 2026-11-24 — Airflow 2.11.2 standalone: scheduled run + clean run green; injected failure halted marts, clear-only recovery completed idempotently (raw untouched); bounded backfill via `dag_run.conf` green; €0 · [Roadmap](../README.md) · [Design](docs/design.md) · [Implementation plan](docs/implementation.md) · [Delivery plan](../docs/delivery-plan.md) · [ADR-0003](../docs/adr/ADR-0003-airflow-vs-dagster.md) · [Evidence](evidence/e07-acceptance.md)

Orchestrate the end-to-end warehouse pipeline (`ingest -> source freshness -> dbt snapshot -> dbt build -> revenue audit`) with **Apache Airflow** running locally in an isolated `uv` environment (plus an optional Docker Compose definition), and document failure recovery and orchestrator trade-offs.

## Deliverables

- Layered Airflow DAG (`charging_commerce_daily`) invoking the isolated `dbt` / ingestion CLI commands, with constant per-source ingest batch ids (`e06-raw-load-<source>`, E01 idempotency) and `dag_run.conf` bounded-backfill windows (`backfill_start`/`backfill_end`, `target`) passed to dbt as `--vars`.
- Architecture Decision Record comparing **Apache Airflow** (this project) vs **Dagster** ([Mlops-engineering M08](../../Mlops-engineering/08-orchestration-dagster/README.md)) on asset lineage, backfill ergonomics, and operational footprint.
- Local runbook covering failed-task triage, downstream blocking, and single-task-group recovery.

## Acceptance

1. A full scheduled/backfilled DAG run succeeds locally from raw ingestion through BigQuery/DuckDB marts with recorded run IDs and task durations.
2. Injecting a bad raw row halts mart publication at the first failing dbt test (accepted values) without touching marts; `verify_revenue_conservation` stays `upstream_failed`.
3. Fixing the input and clearing only the failed stage (`tasks clear -t ... --downstream --only-failed`) completes the run idempotently — upstream producers keep `try_number=1` and no raw rows are re-ingested.
