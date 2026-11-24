"""E08: the template-onboarded second workload must keep building cleanly.

Runs the full `examples/ecb_fx_mart` vertical slice (seed -> staging ->
contract-enforced mart -> tests) into a disposable DuckDB file. This is the
regression guard for the extracted template: if someone changes the example
or the conventions it demonstrates, CI fails here — and the primary
`charging_commerce` project is untouched by construction.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import duckdb
import pytest

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "examples" / "ecb_fx_mart" / "dbt_project"
TEMPLATE = REPO / "template"


def _dbt(*args: str, env_path: Path) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("dbt")
    assert executable, "dbt executable not found in test environment"
    merged = os.environ.copy()
    merged["ECB_FX_DUCKDB"] = str(env_path)
    return subprocess.run(  # noqa: S603 - fixed argv, test-local
        [
            executable,
            *args,
            "--project-dir",
            str(EXAMPLE),
            "--profiles-dir",
            str(EXAMPLE),
            "--target",
            "duckdb",
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
        env=merged,
        timeout=600,
    )


@pytest.fixture(scope="module")
def fx_warehouse(tmp_path_factory) -> Path:
    warehouse = tmp_path_factory.mktemp("ecb_fx") / "fx.duckdb"
    build = _dbt("build", env_path=warehouse)
    assert build.returncode == 0, build.stdout[-2000:] + build.stderr[-2000:]
    return warehouse


def test_template_example_builds_green(fx_warehouse):
    con = duckdb.connect(str(fx_warehouse), read_only=True)
    try:
        rows = con.execute("select count(*) from stg.stg_ecb_fx_rates").fetchone()[0]
        mart = con.execute("select count(*) from mart.fct_fx_rates_daily").fetchone()[0]
        pairs = con.execute(
            "select count(distinct currency_pair) from mart.fct_fx_rates_daily"
        ).fetchone()[0]
    finally:
        con.close()
    assert rows == mart == 507, "grain preservation: staging rows == mart rows"
    assert pairs == 3, "the locked slice carries EUR/CHF, EUR/PLN, EUR/USD"


def test_template_example_contract_is_enforced():
    """The mart contract from the template convention must stay enforced."""
    schema = (EXAMPLE / "models" / "marts" / "schema.yml").read_text(encoding="utf-8")
    assert "enforced: true" in schema
    # ...and the second workload must not reach into the primary's models.
    for sql in (EXAMPLE / "models").rglob("*.sql"):
        assert "charging_commerce" not in sql.read_text(encoding="utf-8"), sql


def test_template_stays_self_contained():
    """The template must not import or reference the primary warehouse's project.

    Prose (README) may name `charging_commerce` for context; config and SQL
    must not.
    """
    for path in TEMPLATE.rglob("*"):
        if path.suffix in {".sql", ".yml", ".toml"}:
            assert "charging_commerce" not in path.read_text(encoding="utf-8"), path
