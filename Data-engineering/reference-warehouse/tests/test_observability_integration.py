"""E08 integration test: audit-dbt against the *real* dbt artifacts.

The unit tests in test_observability.py use synthetic artifacts; this one
parses the actual ``run_results.json`` / ``sources.json`` written by the
session warehouse build (conftest ``warehouse`` fixture), so artifact-shape
drift in dbt upgrades is caught by CI. Reuses the shared session fixture —
no extra dbt invocation.
"""

from __future__ import annotations

import duckdb
import pytest
from conftest import DBT_PROJECT

from charging_commerce import observability


def test_audit_real_dbt_artifacts(warehouse, tmp_path):
    run_results = DBT_PROJECT / "target" / "run_results.json"
    sources = DBT_PROJECT / "target" / "sources.json"
    if not (run_results.is_file() and sources.is_file()):
        pytest.skip("dbt artifacts not present (conftest build did not run?)")

    code, alerts = observability.audit_dbt_artifacts(
        tmp_path / "audit.duckdb", run_results, sources
    )

    # The shared artifacts may legitimately hold negative-drill residue
    # (other tests inject stale timestamps and re-run freshness), so the
    # expectation is recomputed from the artifacts themselves: the audit
    # must classify the REAL artifact contents exactly, whatever they hold.
    audit = observability.parse_run_results(run_results)
    verdicts = observability.parse_sources(sources)
    expected_breaches = sum(
        1
        for v in verdicts
        if observability.classify_freshness(
            v, observability.DEFAULT_WARN_HOURS, observability.DEFAULT_ERROR_HOURS
        ).slo_status
        == "BREACH"
    )
    expected_code = 2 if (audit.failed_count or expected_breaches) else 0
    assert code == expected_code
    assert {a["alert"] for a in alerts} <= {"dbt_node_failed", "freshness_slo"}
    assert len([a for a in alerts if a["alert"] == "dbt_node_failed"]) == audit.failed_count

    con = duckdb.connect(str(tmp_path / "audit.duckdb"))
    try:
        (audit_rows,) = con.execute(
            f"select count(*) from {observability.OPS_SCHEMA}.{observability.RUN_AUDIT_TABLE}"
        ).fetchone()
        (fresh_rows,) = con.execute(
            f"select count(*) from {observability.OPS_SCHEMA}.{observability.FRESHNESS_TABLE}"
        ).fetchone()
        (breaches,) = con.execute(
            f"select count(*) from {observability.OPS_SCHEMA}.{observability.FRESHNESS_TABLE} "
            "where slo_status = 'BREACH'"
        ).fetchone()
        (slowest,) = con.execute(
            f"select max(execution_time_s) from {observability.OPS_SCHEMA}"
            f".{observability.RUN_AUDIT_TABLE}"
        ).fetchone()
    finally:
        con.close()

    assert audit_rows == len(audit.nodes) > 0, "every node of the real build must be audited"
    assert fresh_rows == len(verdicts) >= 5, "the five non-roaming raw sources are audited"
    assert breaches == expected_breaches
    assert slowest > 0


def test_audit_real_artifacts_are_idempotent(warehouse, tmp_path):
    run_results = DBT_PROJECT / "target" / "run_results.json"
    sources = DBT_PROJECT / "target" / "sources.json"
    if not (run_results.is_file() and sources.is_file()):
        pytest.skip("dbt artifacts not present (conftest build did not run?)")

    db = tmp_path / "audit.duckdb"

    def counts():
        con = duckdb.connect(str(db))
        try:
            return con.execute(
                f"select (select count(*) from {observability.OPS_SCHEMA}"
                f".{observability.RUN_AUDIT_TABLE}), (select count(*) from "
                f"{observability.OPS_SCHEMA}.{observability.FRESHNESS_TABLE})"
            ).fetchone()
        finally:
            con.close()

    observability.audit_dbt_artifacts(db, run_results, sources)
    once = counts()
    observability.audit_dbt_artifacts(db, run_results, sources)
    twice = counts()
    assert once == twice and once[0] > 0 and once[1] > 0
