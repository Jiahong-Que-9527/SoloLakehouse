"""E07: DAG integrity tests for `charging_commerce_daily`.

These run inside the isolated Airflow environment
(`reference-warehouse/airflow`, see `uv run --locked pytest ../tests/
test_airflow_dag.py` from there) and are skipped in the main warehouse
environment, which intentionally does not install apache-airflow (design §4:
the DAG must parse in CI without running the Airflow daemon or sharing the
dbt environment).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("airflow", reason="requires the isolated airflow env (airflow/pyproject.toml)")

# DagBag only parses files; it never touches the metadata DB. Point
# AIRFLOW_HOME at a disposable dir so the test works on any machine.
os.environ.setdefault("AIRFLOW_HOME", tempfile.mkdtemp(prefix="slh-airflow-test-"))

from airflow.models.dagbag import DagBag  # noqa: E402

DAGS_DIR = Path(__file__).resolve().parents[1] / "airflow" / "dags"
DAG_ID = "charging_commerce_daily"
EXPECTED_CHAIN = [
    "ingest_raw",
    "dbt_source_freshness",
    "dbt_snapshot",
    "dbt_build_marts",
    "verify_revenue_conservation",
]


@pytest.fixture(scope="module")
def dagbag() -> DagBag:
    return DagBag(dag_folder=str(DAGS_DIR), include_examples=False)


def test_dagbag_has_zero_import_errors(dagbag: DagBag) -> None:
    assert dagbag.import_errors == {}, dagbag.import_errors


def test_dag_is_registered(dagbag: DagBag) -> None:
    assert DAG_ID in dagbag.dags


def test_dag_scheduling_config(dagbag: DagBag) -> None:
    dag = dagbag.dags[DAG_ID]
    assert dag.catchup is False
    assert dag.max_active_runs == 1
    assert dag.tags  # discoverable in the UI


def test_task_chain_matches_design(dagbag: DagBag) -> None:
    """ingest -> freshness -> snapshot -> build -> verify (design §3)."""
    dag = dagbag.dags[DAG_ID]
    assert set(dag.task_ids) == set(EXPECTED_CHAIN)
    for upstream, downstream in zip(EXPECTED_CHAIN, EXPECTED_CHAIN[1:], strict=False):
        assert downstream in dag.get_task(upstream).downstream_task_ids


def test_retry_policy_matches_design(dagbag: DagBag) -> None:
    """retries=1 only on transient ingestion; quality gates fail loudly."""
    dag = dagbag.dags[DAG_ID]
    assert dag.get_task("ingest_raw").retries == 1
    retry_zero_tasks = (
        "dbt_source_freshness",
        "dbt_snapshot",
        "dbt_build_marts",
        "verify_revenue_conservation",
    )
    for task_id in retry_zero_tasks:
        assert dag.get_task(task_id).retries == 0


def test_tasks_are_isolated_uv_invocations(dagbag: DagBag) -> None:
    """Every task must go through the isolated reference-warehouse uv env."""
    dag = dagbag.dags[DAG_ID]
    for task_id in dag.task_ids:
        assert "uv run --locked" in dag.get_task(task_id).bash_command
