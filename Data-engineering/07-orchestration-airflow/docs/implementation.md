# Implementation plan: E07 · Orchestration with Apache Airflow

**Status:** planned. [Brief](../README.md) · [Design](design.md) · [Delivery plan](../../docs/delivery-plan.md)

## First delivery

Stand up an isolated `uv`-managed Apache Airflow environment inside `reference-warehouse/airflow/`, implement the `charging_commerce_daily` DAG driving `charging-commerce` and `dbt`, pass DAG parse tests in CI, run a local failure-and-recovery drill, and write the Airflow vs Dagster ADR.

## Files and modules to create or update

- `Data-engineering/reference-warehouse/airflow/pyproject.toml` & `uv.lock` (`apache-airflow` pinned for Python 3.12)
- `Data-engineering/reference-warehouse/airflow/dags/charging_commerce_dag.py`
- `Data-engineering/reference-warehouse/airflow/docker-compose.yml` (optional reproducible Compose wrapper)
- `Data-engineering/reference-warehouse/tests/test_airflow_dag.py`
- `Data-engineering/docs/adr/ADR-0003-airflow-vs-dagster.md`
- `Data-engineering/07-orchestration-airflow/evidence/e07-acceptance.md`

## Implementation sequence

1. **Isolated Airflow environment:** Initialize `airflow/pyproject.toml` (`requires-python = ">=3.12,<3.13"`, `apache-airflow`) and lock dependencies separately from `reference-warehouse/pyproject.toml`.
2. **Implement `charging_commerce_daily` DAG:** Define tasks `ingest_raw`, `dbt_source_freshness`, `dbt_snapshot`, `dbt_build_marts`, and `verify_revenue_conservation` passing `{{ ds }}` and `dag_run.conf` overrides cleanly to the isolated `reference-warehouse` `uv` environment.
3. **CI DAG integrity test (`test_airflow_dag.py`):** Verify DAG topology, task dependencies, retry policies (`retries=0` on quality/contract tasks), and zero `DagBag` import errors.
4. **Local standalone run + failure/recovery drill:** Start `airflow standalone` in disposable `AIRFLOW_HOME`, record one clean full run, then inject a bad/stale batch to fail `dbt_source_freshness` (confirm downstream blocked), fix input, clear only the failed task, and verify clean completion.
5. **Write ADR & evidence:** Author `docs/adr/ADR-0003-airflow-vs-dagster.md` (next free number in the [ADR index](../../adr/README.md)) comparing Airflow (this warehouse) vs Dagster ([Mlops-engineering M08](../../../Mlops-engineering/08-orchestration-dagster/README.md)) and record run IDs/logs in `evidence/e07-acceptance.md`.

## Verification commands and negative drills

```bash
cd Data-engineering/reference-warehouse/airflow
uv sync --locked --python 3.12
uv run --locked pytest ../tests/test_airflow_dag.py -v
# Local standalone run (disposable AIRFLOW_HOME outside repo):
# AIRFLOW_HOME=/tmp/slh-airflow uv run --locked airflow standalone
```

**Negative drill:** Inject an intentionally failing `dbt_source_freshness` or contract error, confirm `dbt_build_marts` and `verify_revenue_conservation` enter `upstream_failed`, repair input, clear the failed task, and verify clean completion without duplicating raw rows.

## Acceptance evidence

Record in `07-orchestration-airflow/evidence/e07-acceptance.md`: `airflow` / `dbt` versions, full run ID and task duration table, failure-stop + single-task clear recovery timestamps, and backfill run log.
