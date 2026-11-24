# ADR-0003 · Orchestration: Apache Airflow (this track) vs Dagster (M08)

**Status:** Accepted (2026-11-24, E07) · Supersedes: none

## Context

Both tracks of the portfolio need orchestration of the *same shape of pipeline* —
deterministic, CLI-driven stages with explicit data-quality gates — but the two
tracks optimize for different demonstration goals:

- **Data-engineering (this track):** a batch warehouse pipeline
  (`ingest → source freshness → dbt snapshot → dbt build → revenue audit`)
  whose orchestration must show the industry-default scheduler skillset:
  task DAGs, `{{ ds }}` logical-date partitioning, catchup/backfill semantics,
  and clear-task recovery. [Mlops-engineering M08](../../../Mlops-engineering/08-orchestration-dagster/README.md)
  already demonstrates **Dagster** on the ML side, so the portfolio as a whole
  covers both tools regardless of this choice.
- Everything runs locally in WSL2 under the €0 rule (AGENTS.md); Cloud
  Composer and any managed scheduler are out of scope.

## Decision

Use **Apache Airflow 2.11** (isolated `uv` environment in
`reference-warehouse/airflow/`, SQLite metadata, `airflow standalone`) with a
single DAG `charging_commerce_daily` whose tasks are `BashOperator` shells into
the separate reference-warehouse `uv` environment (`uv run --locked`). The DAG
passes the logical date as the ingestion batch id and forwards bounded
backfill windows from `dag_run.conf` to dbt `--vars`.

## Consequences

- **Airflow never shares Python packages with dbt-core.** The DAG env
  (`airflow/pyproject.toml`, its own lock) is separate from
  `reference-warehouse/pyproject.toml`; tasks re-enter the warehouse env via
  `uv run --locked`, which also pins every dbt invocation to the same locked
  versions a developer gets locally.
- **Logical-date semantics drive idempotency**, not Airflow features: the
  E01 state-dir checkpoints make a per-`ds` batch a no-op on rerun, so
  scheduled reruns and `airflow dags backfill -s -e` windows are idempotent
  without any Airflow-side dedup code.
- **Quality gates fail loudly:** `retries=0` on freshness/build/verify tasks
  (a bad batch must not be retried into the marts); only transient ingestion
  gets `retries=1`.
- **Operational footprint is deliberately small:** SequentialExecutor +
  SQLite is sufficient for one 5-task DAG and keeps the local story simple;
  scaling out (Celery/K8s executors, Airflow 3, remote metadata) is a
  deployment concern outside the €0 boundary and is not exercised here.
- **Portfolio coverage:** Dagster asset graphs, sensors and run-keys remain
  demonstrated by M08; interviewers see both paradigms — task-centric
  scheduling (Airflow, data engineering) and asset-centric lineage (Dagster,
  ML pipelines).

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| **Dagster** (software-defined assets over the dbt models) | Best-in-class asset lineage and partition backfills, and it would deduplicate the freshness/conservation gates as asset checks — but M08 already demonstrates it on this portfolio; using it here again would hide the industry-default Airflow skillset (scheduler semantics, clear/retry drill, catchup backfills) that E07 exists to show. |
| `astronomer-cosmos` (render dbt DAG as Airflow tasks) | Strong choice for many-model projects, but it re-expresses dbt's own DAG inside Airflow and hides the deliberate two-phase `run → build` ordering (fresh-warehouse unit-test constraint, E05/E06) behind generated tasks; five explicit tasks keep the contract gates legible. |
| cron + shell scripts | No run history, no state visualization, no clear-task recovery, no backfill primitive — the exact gaps E07 must close. |
| Cloud Composer / MWAA | Violates the €0 / Free-Tier rule (AGENTS.md §GCP cost gate); explicitly out of scope in design §1. |
| Prefect | Would add a third orchestrator paradigm to the portfolio without demonstrating anything M08 or Airflow already cover. |
