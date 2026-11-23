"""Shared E02+/E03 test fixtures and helpers.

The session-scoped ``warehouse`` fixture runs the full offline loop on a
disposable DuckDB file: generate → ingest (all six sources, roaming through the
in-process mock API) → `dbt source freshness` → `dbt build --target duckdb`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import duckdb
import pytest

from charging_commerce import ingestion
from charging_commerce.generator import MockRoamingServer, generate

REPO = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO / "fixtures"
DBT_PROJECT = REPO / "dbt_project"

GENERATED_SOURCES = {"bnetza", "tariffs", "sessions"}


def _dbt(
    *args: str,
    env: dict[str, str] | None = None,
    project_dir: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("dbt")
    assert executable, "dbt executable not found in test environment"
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    final_args = list(args)
    if "--project-dir" not in final_args:
        final_args += ["--project-dir", str(project_dir or DBT_PROJECT)]
    return subprocess.run(  # noqa: S603 - fixed argv, test-local
        [
            executable,
            *final_args,
            "--profiles-dir",
            str(DBT_PROJECT),
            "--target",
            "duckdb",
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
        env=merged_env,
        timeout=600,
    )


def _query(db_path: Path, sql: str):
    conn = duckdb.connect(str(db_path))
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def _scalar(db_path: Path, sql: str):
    conn = duckdb.connect(str(db_path))
    try:
        return conn.execute(sql).fetchone()[0]
    finally:
        conn.close()


def _build_raw_warehouse(tmp: Path) -> Path:
    """Generate + ingest all six sources into a fresh DuckDB file."""
    gen_dir, db_path, state_dir = tmp / "generated", tmp / "warehouse.duckdb", tmp / "state"
    generate(gen_dir, FIXTURES_DIR)
    for source, batch in (
        ("bnetza", "bnetza-snapshots-0001"),
        ("tariffs", "tariffs-t0t1t2-0001"),
        ("sessions", "charging-sim-window-0001"),
        ("smard", "smard-2025-10-2026-05-0001"),
        ("ecb", "ecb-2025-09-2026-05-0001"),
    ):
        name = ingestion.SOURCE_PAYLOADS[source]
        payload = gen_dir / name if source in GENERATED_SOURCES else FIXTURES_DIR / name
        ingestion.ingest_file(source, payload, batch, db_path, state_dir)
    # Roaming flows through the in-process mock API so all six raw sources are fresh.
    server = MockRoamingServer(gen_dir / "settlements.jsonl", gen_dir / "roaming_faults.json")
    server.start()
    try:
        ingestion.ingest_roaming(server.base_url, "roaming-window-0001", db_path, state_dir)
    finally:
        server.stop()
    return db_path


@pytest.fixture(scope="session")
def warehouse(tmp_path_factory) -> Path:
    """Fresh raw warehouse + snapshot history + full dbt build; shared by all dbt-facing tests."""
    tmp = tmp_path_factory.mktemp("dbt")
    db_path = _build_raw_warehouse(tmp)

    env = {"CHARGING_COMMERCE_DUCKDB": str(db_path)}
    deps = _dbt("deps", env=env)
    assert deps.returncode == 0, deps.stdout[-2000:] + deps.stderr[-2000:]
    freshness = _dbt("source", "freshness", env=env)
    assert freshness.returncode == 0, freshness.stdout[-2000:] + freshness.stderr[-2000:]

    # SCD2 simulated time: build the staging views the snapshots read, then
    # replay the raw snapshot dates in order (t0 → t1 → t2). Models build
    # before the test-bearing `dbt build` so the incremental fct relation
    # exists for the golden unit test's `this` mock.
    stg = _dbt("run", "--select", "stg_bnetza_stations stg_tariff_plans", env=env)
    assert stg.returncode == 0, stg.stdout[-2000:] + stg.stderr[-2000:]
    for asof in ("2025-09-15", "2026-01-15", "2026-05-15"):
        snap = _dbt("snapshot", "--vars", f'{{"snapshot_asof": "{asof}"}}', env=env)
        assert snap.returncode == 0, snap.stdout[-2000:] + snap.stderr[-2000:]
    run_models = _dbt("run", env=env)
    assert run_models.returncode == 0, run_models.stdout[-2000:] + run_models.stderr[-2000:]

    build = _dbt("build", env=env)
    assert build.returncode == 0, build.stdout[-4000:] + build.stderr[-4000:]
    return db_path
