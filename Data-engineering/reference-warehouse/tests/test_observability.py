"""E08 acceptance tests: dbt artifact observability (ops_* audit tables + SLO drill).

All fixtures are synthetic minimal dbt artifacts written to tmp_path, so the
drills (stale source, failed node, idempotent replay) run fully offline and
never depend on a prior dbt invocation.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import duckdb

from charging_commerce import observability
from charging_commerce.cli import main as cli_main

# Fixed "now" used across every fixture so lag arithmetic is deterministic.
SNAPSHOT_AT = "2026-11-24T20:00:00+00:00"
_RECORDED = datetime.fromisoformat(SNAPSHOT_AT).astimezone(UTC).replace(tzinfo=None)


def _write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _run_results(path, invocation="inv-0001", nodes=None):
    """Minimal run_results.json: by default one success model + one failing test."""
    return _write_json(
        path,
        {
            "metadata": {"invocation_id": invocation, "dbt_version": "1.12.7"},
            "results": nodes
            or [
                {
                    "unique_id": "model.charging_commerce.fct_daily_revenue_v2",
                    "status": "success",
                    "execution_time": 12.5,
                    "timing": [
                        {
                            "name": "execute",
                            "started_at": "2026-11-24T19:59:40+00:00",
                            "completed_at": "2026-11-24T19:59:53+00:00",
                        }
                    ],
                    "node": {"name": "fct_daily_revenue_v2", "resource_type": "model"},
                },
                {
                    "unique_id": "test.charging_commerce.assert_revenue_conservation",
                    "status": "fail",
                    "execution_time": 2.8,
                    "failures": 1,
                    "timing": [
                        {
                            "name": "execute",
                            "started_at": "2026-11-24T19:59:53+00:00",
                            "completed_at": "2026-11-24T19:59:56+00:00",
                        }
                    ],
                    "node": {
                        "name": "assert_revenue_conservation",
                        "resource_type": "test",
                    },
                },
            ],
        },
    )


def _sources(path, invocation="srcinv-0001", sources=None):
    """Minimal sources.json: by default one fresh (2h lag) and one breaching (>48h)."""
    return _write_json(
        path,
        {
            "metadata": {"invocation_id": invocation},
            "results": sources
            or [
                {
                    "unique_id": "source.charging_commerce.raw.raw_charging_sessions",
                    "name": "raw_charging_sessions",
                    "status": "pass",
                    "max_loaded_at": "2026-11-24T18:00:00+00:00",  # 2h lag -> PASS
                    "snapshotted_at": SNAPSHOT_AT,
                },
                {
                    "unique_id": "source.charging_commerce.raw.raw_smard_prices",
                    "name": "raw_smard_prices",
                    "status": "pass",
                    "max_loaded_at": "2026-11-22T12:00:00+00:00",  # 56h lag -> BREACH
                    "snapshotted_at": SNAPSHOT_AT,
                },
            ],
        },
    )


def _rows(db, sql):
    con = duckdb.connect(str(db))
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


# ---------------------------------------------------------------- run audit


def test_run_audit_records_nodes_and_is_idempotent(tmp_path):
    db = tmp_path / "w.duckdb"
    artifact = _run_results(tmp_path / "run_results.json")

    first = observability.audit_run_results(duckdb.connect(str(db)), artifact, git_sha="abc123")
    assert first.invocation_id == "inv-0001"
    assert len(first.nodes) == 2
    assert first.failed_count == 1
    assert first.failures[0].unique_id.endswith("assert_revenue_conservation")

    con = duckdb.connect(str(db))
    observability.audit_run_results(con, artifact)  # same artifact again (task retry)
    con.close()

    rows = _rows(
        db,
        f"select unique_id, status, execution_time_s, git_sha from {observability.OPS_SCHEMA}"
        f".{observability.RUN_AUDIT_TABLE} order by unique_id",
    )
    assert len(rows) == 2, "re-parsing the same invocation must not duplicate rows"
    failed = [r for r in rows if r[0].endswith("assert_revenue_conservation")][0]
    assert failed[1] == "fail" and failed[2] == 2.8
    succeeded = [r for r in rows if r[0].endswith("fct_daily_revenue_v2")][0]
    assert succeeded[1] == "success"
    # The retry re-parse carried no git_sha, so the PK replace overwrote the
    # first write's value — documented replace semantics, not a duplicate.


# ------------------------------------------------------- freshness SLO drill


def test_freshness_pass_warn_breach_and_alerts(tmp_path):
    db = tmp_path / "w.duckdb"
    con = duckdb.connect(str(db))
    artifact = _sources(tmp_path / "sources.json")
    verdicts = {v.verdict.unique_id: v for v in observability.audit_sources(con, artifact)}
    con.close()

    fresh = verdicts["source.charging_commerce.raw.raw_charging_sessions"]
    stale = verdicts["source.charging_commerce.raw.raw_smard_prices"]
    assert fresh.slo_status == "PASS" and fresh.lag_hours == 2.0 and fresh.alert is None
    assert stale.slo_status == "BREACH"
    assert stale.lag_hours == 56.0
    assert stale.alert["level"] == "BREACH"
    assert stale.alert["threshold_hours"] == 48.0

    # A 30h lag lands in the WARN band (24h < lag <= 48h) with its own payload.
    warn = observability.classify_freshness(
        observability.SourceFreshness(
            unique_id="source.x.raw.raw_ecb_fx_rates",
            source_name="raw_ecb_fx_rates",
            freshness_status="pass",
            max_loaded_at=_RECORDED - timedelta(hours=30),
            snapshotted_at=_RECORDED,
        ),
        observability.DEFAULT_WARN_HOURS,
        observability.DEFAULT_ERROR_HOURS,
    )
    assert warn.slo_status == "WARN" and warn.alert["level"] == "WARN"
    assert warn.alert["threshold_hours"] == 24.0


def test_freshness_dbt_error_status_is_breach_even_without_lag(tmp_path):
    db = tmp_path / "w.duckdb"
    artifact = _sources(
        tmp_path / "sources.json",
        sources=[
            {
                "unique_id": "source.charging_commerce.raw.raw_roaming_settlements",
                "name": "raw_roaming_settlements",
                "status": "error",  # missing relation (E05 boundary drill shape)
                "max_loaded_at": None,
                "snapshotted_at": SNAPSHOT_AT,
            }
        ],
    )
    con = duckdb.connect(str(db))
    (verdict,) = observability.audit_sources(con, artifact)
    con.close()
    assert verdict.slo_status == "BREACH"
    assert verdict.alert["level"] == "BREACH" and verdict.lag_hours is None


def test_freshness_reparse_is_idempotent(tmp_path):
    db = tmp_path / "w.duckdb"
    artifact = _sources(tmp_path / "sources.json")
    con = duckdb.connect(str(db))
    observability.audit_sources(con, artifact)
    observability.audit_sources(con, artifact)  # same invocation_id again
    con.close()
    rows = _rows(
        db, f"select count(*) from {observability.OPS_SCHEMA}.{observability.FRESHNESS_TABLE}"
    )
    assert rows == [(2,)]


# ------------------------------------------------------------ full CLI audit


def test_audit_dbt_artifacts_exit_codes_and_alerts(tmp_path):
    db = tmp_path / "w.duckdb"
    rr, src = _run_results(tmp_path / "run_results.json"), _sources(tmp_path / "sources.json")

    code, alerts = observability.audit_dbt_artifacts(db, rr, src)
    assert code == 2, "a failed test node AND a freshness breach both escalate to exit 2"
    kinds = {a["alert"] for a in alerts}
    assert kinds == {"dbt_node_failed", "freshness_slo"}

    # Fresh artifacts only -> PASS everywhere, exit 0.
    fresh_src = _sources(
        tmp_path / "sources_fresh.json",
        sources=[
            {
                "unique_id": "source.charging_commerce.raw.raw_charging_sessions",
                "name": "raw_charging_sessions",
                "status": "pass",
                "max_loaded_at": "2026-11-24T19:00:00+00:00",
                "snapshotted_at": SNAPSHOT_AT,
            }
        ],
    )
    ok_rr = _run_results(
        tmp_path / "run_results_ok.json",
        nodes=[
            {
                "unique_id": "model.charging_commerce.fct_daily_revenue_v2",
                "status": "success",
                "execution_time": 12.5,
                "timing": [],
                "node": {"name": "fct_daily_revenue_v2", "resource_type": "model"},
            }
        ],
    )
    code, alerts = observability.audit_dbt_artifacts(db, ok_rr, fresh_src)
    assert code == 0 and alerts == []

    # WARN-only sources -> exit 1.
    warn_src = _sources(
        tmp_path / "sources_warn.json",
        sources=[
            {
                "unique_id": "source.charging_commerce.raw.raw_ecb_fx_rates",
                "name": "raw_ecb_fx_rates",
                "status": "pass",
                "max_loaded_at": "2026-11-23T14:00:00+00:00",  # 30h -> WARN
                "snapshotted_at": SNAPSHOT_AT,
            }
        ],
    )
    code, alerts = observability.audit_dbt_artifacts(db, None, warn_src)
    assert code == 1 and [a["level"] for a in alerts] == ["WARN"]


def test_audit_dbt_artifacts_requires_at_least_one_artifact(tmp_path):
    try:
        observability.audit_dbt_artifacts(tmp_path / "w.duckdb")
        raise AssertionError("expected SystemExit")
    except SystemExit as exc:
        assert "neither run_results nor sources" in str(exc)


def test_cli_audit_dbt_writes_ops_tables_and_exit_code(tmp_path, monkeypatch, capsys):
    db = tmp_path / "w.duckdb"
    rr = _run_results(tmp_path / "run_results.json")
    src = _sources(tmp_path / "sources.json")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_SHA", "deadbee")

    code = cli_main(
        [
            "audit-dbt",
            "--run-results",
            str(rr),
            "--sources",
            str(src),
            "--db",
            str(db),
        ]
    )
    assert code == 2
    out = capsys.readouterr().out
    lines = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
    assert {a["alert"] for a in lines} == {"dbt_node_failed", "freshness_slo"}

    audit_rows = _rows(
        db,
        f"select count(*), count(distinct git_sha) from {observability.OPS_SCHEMA}"
        f".{observability.RUN_AUDIT_TABLE}",
    )
    assert audit_rows == [(2, 1)]
    breach_rows = _rows(
        db,
        f"select count(*) from {observability.OPS_SCHEMA}.{observability.FRESHNESS_TABLE} "
        "where slo_status = 'BREACH'",
    )
    assert breach_rows == [(1,)]
