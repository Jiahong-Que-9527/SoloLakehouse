"""E05 acceptance tests: Slim CI selection, doc coverage, exposures.

Simulates the GitHub Actions Slim CI flow locally: a baseline manifest from a
full build plays the role of the `main` artifact; project copies with an edited
downstream mart or an upstream staging model must select exactly the expected
`state:modified+` node set, and a fresh-env slim build must execute exactly the
impacted subgraph (modified + ancestors + descendants).
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest
from conftest import DBT_PROJECT, _dbt


def _baseline_state(tmp_path) -> Path:
    """Baseline manifest = the artifact `main` would have uploaded. CI restores
    it from the prod-state artifact (PROD_STATE_DIR); locally it is the fixture's
    own build manifest."""
    state = tmp_path / "prod_state"
    state.mkdir()
    env_state = os.environ.get("PROD_STATE_DIR")
    source = (
        Path(env_state) / "manifest.json" if env_state else DBT_PROJECT / "target" / "manifest.json"
    )
    shutil.copy(source, state / "manifest.json")
    return state


def _modified_project(tmp_path, rel_path: str, mutation) -> Path:
    project_copy = tmp_path / "project_modified"
    shutil.copytree(
        DBT_PROJECT,
        project_copy,
        ignore=shutil.ignore_patterns("target", "logs", ".user.yml"),
    )
    target = project_copy / rel_path
    mutated = mutation(target.read_text())
    assert mutated != target.read_text(), "mutation must change the file"
    target.write_text(mutated)
    return project_copy


def _slim_selected_models(tmp_path, project_copy: Path, state: Path, env) -> set[str]:
    result = _dbt(
        "ls",
        "--select",
        "state:modified+",
        "--state",
        str(state),
        "--resource-type",
        "model",
        "--output",
        "name",
        "--project-dir",
        str(project_copy),
        env=env,
    )
    assert result.returncode == 0, result.stdout[-2000:]
    import re as _re

    ansi = _re.compile(r"\x1b\[[0-9;]*m")
    name_re = _re.compile(r"^[a-z_]+(\.v\d+)?$")
    return {
        name
        for line in result.stdout.splitlines()
        for name in [ansi.sub("", line).strip()]
        if name_re.match(name)
    }


def test_downstream_edit_selects_only_changed_mart(warehouse, tmp_path):
    """Editing a leaf mart selects just that mart (design §5.1)."""
    state = _baseline_state(tmp_path)
    project = _modified_project(
        tmp_path,
        "models/marts/fct_daily_revenue_v2.sql",
        lambda sql: sql + "\n-- slim-ci downstream drill\n",
    )
    selected = _slim_selected_models(
        tmp_path, project, state, {"CHARGING_COMMERCE_DUCKDB": str(warehouse)}
    )
    assert selected == {"fct_daily_revenue.v2"}


def test_upstream_edit_fans_out_to_downstream(warehouse, tmp_path):
    """Editing an upstream staging model selects the full impacted path (design §5.2)."""
    state = _baseline_state(tmp_path)
    project = _modified_project(
        tmp_path,
        "models/staging/stg_ecb_fx.sql",
        lambda sql: sql + "\n-- slim-ci upstream drill\n",
    )
    selected = _slim_selected_models(
        tmp_path, project, state, {"CHARGING_COMMERCE_DUCKDB": str(warehouse)}
    )
    assert selected == {
        "stg_ecb_fx",
        "int_sessions_enriched_fx",
        "int_sessions_wholesale_cost",
        "fct_charging_sessions",
        "fct_daily_revenue.v1",
        "fct_daily_revenue.v2",
    }


def test_slim_build_on_fresh_env_executes_impacted_subgraph(warehouse, tmp_path):
    """`dbt build --select +state:modified+ --defer --state` on the ephemeral duckdb
    executes exactly modified + ancestors + descendants — the CI PR pattern."""
    state = _baseline_state(tmp_path)
    project = _modified_project(
        tmp_path,
        "models/staging/stg_ecb_fx.sql",
        lambda sql: sql + "\n-- slim-ci upstream drill\n",
    )
    result = _dbt(
        "build",
        "--select",
        "+state:modified+",
        "--defer",
        "--state",
        str(state),
        "--project-dir",
        str(project),
        env={"CHARGING_COMMERCE_DUCKDB": str(warehouse)},
    )
    assert result.returncode == 0, result.stdout[-3000:]

    run_results = json.loads((project / "target" / "run_results.json").read_text())
    executed_models = {
        r["unique_id"].replace("model.charging_commerce.", "")
        for r in run_results["results"]
        if r["unique_id"].startswith("model.")
    }
    assert executed_models == {
        "stg_ecb_fx",
        "int_sessions_enriched_fx",
        "int_sessions_wholesale_cost",
        "fct_charging_sessions",
        "fct_daily_revenue.v1",
        "fct_daily_revenue.v2",
    }


# --------------------------------------------------------------------------
# Doc coverage: 100% of mart columns documented (E05 acceptance criterion 1)
# --------------------------------------------------------------------------


def _mart_column_doc_gaps(manifest: dict) -> list[str]:
    gaps = []
    for unique_id, node in manifest["nodes"].items():
        if not (unique_id.startswith("model.") and "/marts/" in node["original_file_path"]):
            continue
        for column_name, meta in (node.get("columns") or {}).items():
            if not (meta.get("description") or "").strip():
                gaps.append(f"{unique_id}.{column_name}")
    return gaps


def test_mart_columns_fully_documented(warehouse):
    manifest = json.loads((DBT_PROJECT / "target" / "manifest.json").read_text())
    exposures = {uid.split(".")[-1] for uid in manifest.get("exposures", {})}
    assert {"charging_revenue_dashboard", "ev_demand_ml_features"} <= exposures, (
        "exposures.yml must declare the BI dashboard and the ML feature exposure"
    )
    gaps = _mart_column_doc_gaps(manifest)
    assert gaps == [], f"undocumented mart columns: {gaps[:5]}"


def test_restored_prod_state_manifest_is_valid(warehouse):
    """CI plumbing check: when the workflow restores a main artifact, it must be
    a parseable manifest covering the full model set. Skipped locally (no
    artifact) — exercised on every PR run after the first main build."""
    import os

    env_state = os.environ.get("PROD_STATE_DIR")
    if not env_state or not (Path(env_state) / "manifest.json").is_file():
        pytest.skip("no restored prod-state artifact (first bootstrap or local run)")
    manifest = json.loads((Path(env_state) / "manifest.json").read_text())
    models = [uid for uid in manifest["nodes"] if uid.startswith("model.")]
    assert len(models) >= 15
    assert manifest["metadata"]["project_name"] == "charging_commerce"


def test_doc_coverage_check_catches_missing_description(warehouse, tmp_path):
    """Negative drill: strip one mart column description -> the check fails."""
    manifest = json.loads((DBT_PROJECT / "target" / "manifest.json").read_text())
    victim_node = next(
        uid
        for uid, node in manifest["nodes"].items()
        if uid.startswith("model.") and "/marts/" in node["original_file_path"] and node["columns"]
    )
    victim_col = sorted(manifest["nodes"][victim_node]["columns"])[0]
    manifest["nodes"][victim_node]["columns"][victim_col]["description"] = ""
    assert _mart_column_doc_gaps(manifest) == [f"{victim_node}.{victim_col}"]
