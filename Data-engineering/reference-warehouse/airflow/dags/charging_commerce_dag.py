"""E07 · `charging_commerce_daily` — the end-to-end warehouse pipeline DAG.

Pipeline (design §3): ingest_raw -> dbt_source_freshness -> dbt_snapshot
-> dbt_build_marts -> verify_revenue_conservation -> audit_dbt_artifacts
(the E08 observability task runs with trigger_rule='all_done' so failed
runs are recorded in the ops_* audit tables too).

Design rules honoured here (07-orchestration-airflow/docs/design.md):

- Isolation: every task shells out to the *reference-warehouse* `uv`
  environment (`uv run --locked`), so Airflow never shares Python packages
  with dbt-core.
- Idempotency: the ingestion batch id is the logical execution date
  (`{{ ds }}`); the E01 state-dir checkpoints make re-ingesting a batch a
  no-op, so scheduled reruns and `airflow dags backfill -s ... -e ...` are
  idempotent.
- Backfills: trigger `conf` may override `backfill_start` / `backfill_end`
  (forwarded to dbt `--vars`, consumed by the contract §3.5 bounded-backfill
  lookback) and `target` (`duckdb` | `bq`).
- Failure semantics: `retries=1` only on the transient ingestion task;
  quality/contract tasks (freshness, build, verify) have `retries=0` so a bad
  batch fails loudly instead of silently retrying into the marts.

Cloud Composer is explicitly out of scope (Free Tier / EUR 0 rule, AGENTS.md).
"""

from __future__ import annotations

import os
from pathlib import Path

from airflow import DAG
from airflow.operators.bash import BashOperator
from pendulum import datetime

# dags/ lives at reference-warehouse/airflow/dags, so the warehouse root is
# two levels up. All tasks run with cwd=REPO so relative defaults (data/,
# dbt_project/) resolve exactly like the documented CLI workflows.
REPO = Path(__file__).resolve().parents[2]
DBT_DIR = REPO / "dbt_project"
WAREHOUSE = os.environ.get("AIRFLOW_WAREHOUSE_PATH", str(REPO / "data" / "warehouse.duckdb"))

# The locked fixture snapshot dates (ADR-0002 simulated time t0 -> t1 -> t2);
# a fresh warehouse replays all three so SCD2 history is complete.
SNAPSHOT_ASOF_DATES = ("2025-09-15", "2026-01-15", "2026-05-15")

# Full environment inheritance (BashOperator with an explicit `env` dict
# *replaces* os.environ, which would drop PATH) plus the pinned warehouse path.
TASK_ENV = {**os.environ, "CHARGING_COMMERCE_DUCKDB": WAREHOUSE}

default_args = {
    "owner": "data-engineering",
    "retries": 0,
    "depends_on_past": False,
}


def _dbt(command: str, extra: str = "") -> str:
    """Render the isolated `uv run` invocation for a dbt command."""
    return (
        f'cd "{REPO}" && '
        f"uv run --locked dbt {command} "
        f'--project-dir "{DBT_DIR}" --profiles-dir "{DBT_DIR}" '
        f"--target {{{{ params.target }}}} {extra}"
    ).strip()


with DAG(
    dag_id="charging_commerce_daily",
    description=(
        "EV charging & roaming commerce warehouse: ingest -> freshness -> "
        "snapshot -> build -> verify -> artifact audit."
    ),
    start_date=datetime(2026, 11, 20, tz="UTC"),
    schedule="0 5 * * *",
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    params={
        "target": "duckdb",
        "backfill_start": None,
        "backfill_end": None,
    },
    tags=["charging-commerce", "e07"],
) as dag:
    # 1) Ingest every locked source. Payload generation runs first as a
    #    fresh-clone bootstrap (only when the payloads are missing:
    #    regeneration is not byte-stable, and E01's state-dir collision
    #    check compares payload hashes, so a re-run must reuse the files
    #    it was recorded against). The batch id is a *constant* per source
    #    (E06 bq_loader convention, "e06-raw-load" prefix): the generated
    #    payloads are a date-locked snapshot of the whole window, so a
    #    per-ds batch id would append the same rows again on every run
    #    with a different logical date and break the raw unique tests.
    #    E01 keys its state file by batch id alone, hence the source
    #    suffix. retries=1 absorbs transient I/O. Roaming stays out (E05
    #    boundary: needs the mock API server).
    ingest_raw = BashOperator(
        task_id="ingest_raw",
        bash_command=(
            f'cd "{REPO}" && '
            "if [ ! -f data/generated/charging_sessions.jsonl ]; then "
            "uv run --locked charging-commerce generate --out-dir data/generated; fi && "
            "for src in bnetza tariffs sessions smard ecb; do "
            'uv run --locked charging-commerce ingest "$src" '
            f'--batch-id e06-raw-load-$src --db "{WAREHOUSE}" || exit 1; done'
        ),
        cwd=str(REPO),
        env=TASK_ENV,
        retries=1,
    )

    # 2) Contract §1 source freshness: hard gate (retries=0). A stale or
    #    missing raw layer must halt publication before any mart is touched.
    #    raw_roaming_settlements is excluded: the E05 boundary keeps roaming
    #    out of this DAG (its collector needs the mock API server), so a
    #    fresh warehouse has no roaming relation at all and dbt reports the
    #    source as an error. Roaming freshness is exercised by the E05
    #    drills against the mock API, not here.
    dbt_source_freshness = BashOperator(
        task_id="dbt_source_freshness",
        bash_command=_dbt(
            "source freshness",
            "--warn-error --exclude source:raw.raw_roaming_settlements",
        ),
        cwd=str(REPO),
        env=TASK_ENV,
        retries=0,
    )

    # 3) SCD2 snapshots (ADR-0002). The snapshot relations read the two
    #    staging views, and a *fresh* warehouse needs the locked as-of
    #    history replayed t0 -> t1 -> t2 (simulated time); every step is
    #    idempotent (unchanged stations keep their original updated_at).
    snapshot_commands = " && ".join(
        _dbt("snapshot", f"--vars 'snapshot_asof: {asof}'") for asof in SNAPSHOT_ASOF_DATES
    )
    dbt_snapshot = BashOperator(
        task_id="dbt_snapshot",
        bash_command=(
            _dbt("run", "--select stg_bnetza_stations stg_tariff_plans")
            + " && "
            + snapshot_commands
        ),
        cwd=str(REPO),
        env=TASK_ENV,
        retries=0,
    )

    # 4) Staging -> intermediate -> marts. `dbt run` first so the incremental
    #    fact relation exists for the golden unit test's `this` mock (E05/E06
    #    documented fresh-warehouse ordering), then the test-bearing build. A
    #    bounded backfill window from the trigger conf is forwarded to dbt
    #    --vars (contract §3.5 lookback).
    dbt_build_marts = BashOperator(
        task_id="dbt_build_marts",
        bash_command=(
            "{% set window = {} %}"
            "{% if params.backfill_start and params.backfill_end %}"
            "{% set window = {'backfill_start': params.backfill_start, "
            "'backfill_end': params.backfill_end} %}"
            "{% endif %}"
            + _dbt("run", "--vars '{{ window | tojson }}'")
            + " && "
            + _dbt("build", "--vars '{{ window | tojson }}'")
        ),
        cwd=str(REPO),
        env=TASK_ENV,
        retries=0,
    )

    # 5) Independent revenue-conservation audit (contract §3.1): recomputes
    #    net_amount_eur straight from raw-layer events, not the mart pipeline.
    verify_revenue_conservation = BashOperator(
        task_id="verify_revenue_conservation",
        bash_command=_dbt("test", "--select assert_revenue_conservation"),
        cwd=str(REPO),
        env=TASK_ENV,
        retries=0,
    )

    # 6) E08 observability: parse the run's dbt artifacts (run_results.json
    #    from the build, sources.json from the freshness gate) into the
    #    warehouse's ops_* audit tables and emit freshness-SLO alerts.
    #    trigger_rule='all_done' is the point: a failed build or a halted
    #    freshness gate is exactly when telemetry matters most, so this task
    #    records the failure rows + breach alerts even when upstream failed.
    audit_dbt_artifacts = BashOperator(
        task_id="audit_dbt_artifacts",
        bash_command=(
            f'cd "{REPO}" && '
            "uv run --locked charging-commerce audit-dbt "
            f'--run-results "{DBT_DIR}/target/run_results.json" '
            f'--sources "{DBT_DIR}/target/sources.json" '
            f'--db "{WAREHOUSE}"'
        ),
        cwd=str(REPO),
        env=TASK_ENV,
        retries=0,
        trigger_rule="all_done",
    )

    (
        ingest_raw
        >> dbt_source_freshness
        >> dbt_snapshot
        >> dbt_build_marts
        >> verify_revenue_conservation
        >> audit_dbt_artifacts
    )
