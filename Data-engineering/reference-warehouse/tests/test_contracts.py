"""E03 acceptance tests: enforced contracts, model versioning, and test gates.

All drills run against disposable copies — the project directory and warehouse
are copied before mutation, so the committed tree and the shared fixture stay
pristine.
"""

from __future__ import annotations

import json
import shutil

from conftest import DBT_PROJECT, _dbt, _query, _scalar


def test_unit_tests_pass(warehouse):
    """Native dbt unit_tests (golden example + reduction/tie-break/DST/FX) all pass."""
    result = _dbt(
        "test",
        "--select",
        "test_type:unit",
        env={"CHARGING_COMMERCE_DUCKDB": str(warehouse)},
    )
    assert result.returncode == 0, result.stdout[-3000:]


def test_v1_v2_coexist_with_additive_diff(warehouse):
    """v1 and v2 both build; v2 = v1 + wholesale_cost_eur + gross_margin_eur."""
    v1_cols = {
        row[0]
        for row in _query(
            warehouse,
            "select column_name from information_schema.columns"
            " where table_schema = 'mart' and table_name = 'fct_daily_revenue_v1'"
            " order by ordinal_position",
        )
    }
    v2_cols = {
        row[0]
        for row in _query(
            warehouse,
            "select column_name from information_schema.columns"
            " where table_schema = 'mart' and table_name = 'fct_daily_revenue_v2'"
            " order by ordinal_position",
        )
    }
    assert v1_cols == {
        "revenue_date",
        "country_code",
        "operator_name",
        "session_count",
        "total_energy_kwh",
        "gross_amount_eur",
        "roaming_fee_eur",
        "net_amount_eur",
    }
    assert v2_cols == v1_cols | {"wholesale_cost_eur", "gross_margin_eur"}
    (v2_rows,) = _query(warehouse, "select count(*) from mart.fct_daily_revenue_v2")[0]
    assert v2_rows > 0


def test_v1_deprecation_and_mart_contracts_in_manifest(warehouse):
    """latest_version=2, v1 carries a deprecation_date, and all five marts enforce contracts."""
    manifest = json.loads((DBT_PROJECT / "target" / "manifest.json").read_text())
    nodes = manifest["nodes"]

    v1 = nodes["model.charging_commerce.fct_daily_revenue.v1"]
    assert str(v1["deprecation_date"]).startswith("2027-02-28")
    assert v1["config"]["contract"]["enforced"] is True

    for name in (
        "dim_date",
        "dim_stations",
        "dim_tariffs",
        "fct_charging_sessions",
        "fct_daily_revenue.v2",
    ):
        node = nodes[f"model.charging_commerce.{name}"]
        assert node["config"]["contract"]["enforced"] is True, name


def test_contract_breach_fails_build_and_preserves_table(warehouse, tmp_path):
    """Retyping a contracted column must fail dbt build — and leave the prior
    mart table intact (contract enforcement guards against bad replacements)."""
    project_copy = tmp_path / "dbt_project_breach"
    shutil.copytree(
        DBT_PROJECT,
        project_copy,
        ignore=shutil.ignore_patterns("target", "logs", ".user.yml"),
    )
    fct_sql = project_copy / "models" / "marts" / "fct_charging_sessions.sql"
    # Valid SQL, wrong type: gross_amount_eur becomes DECIMAL(18,3) instead of the
    # contracted DECIMAL(18,2) — a pure contract breach, not a SQL error.
    mutated = fct_sql.read_text().replace("decimal(18, 2)", "decimal(18, 3)", 1)
    assert mutated != fct_sql.read_text(), "mutation must hit the gross_amount_eur cast"
    fct_sql.write_text(mutated)

    db_copy = tmp_path / "breach.duckdb"
    shutil.copy(warehouse, db_copy)
    type_query = (
        "select data_type from information_schema.columns"
        " where table_schema = 'mart' and table_name = 'fct_charging_sessions'"
        " and column_name = 'gross_amount_eur'"
    )
    before = _scalar(db_copy, type_query)

    result = _dbt(
        "build",
        "--no-partial-parse",
        env={"CHARGING_COMMERCE_DUCKDB": str(db_copy)},
        project_dir=project_copy,
    )
    assert result.returncode != 0, "contract breach must fail dbt build"
    assert "contract" in result.stdout.lower(), result.stdout[-2000:]

    after = _scalar(db_copy, type_query)
    assert after == before, "the previous valid table must be preserved verbatim"
    assert after.upper().replace(" ", "").startswith("DECIMAL(18,2)")


def test_conservation_drift_fails_singular_test(warehouse, tmp_path):
    """A 0.01 EUR drift between fact and the raw-side recomputation fails the
    canonical conservation test (data-contract §3.1, tolerance 0.00)."""
    db_copy = tmp_path / "drift.duckdb"
    shutil.copy(warehouse, db_copy)
    victim = _scalar(db_copy, "select session_id from mart.fct_charging_sessions limit 1")
    conn = None
    try:
        import duckdb

        conn = duckdb.connect(str(db_copy))
        conn.execute(
            "update mart.fct_charging_sessions set net_amount_eur = net_amount_eur + 0.01"
            " where session_id = ?",
            [victim],
        )
    finally:
        if conn is not None:
            conn.close()

    result = _dbt(
        "test",
        "--select",
        "assert_revenue_conservation",
        env={"CHARGING_COMMERCE_DUCKDB": str(db_copy)},
    )
    assert result.returncode != 0, "0.01 EUR drift must fail the conservation gate"
    assert "assert_revenue_conservation" in result.stdout
