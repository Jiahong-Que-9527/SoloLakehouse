"""dbt artifact observability (E08): run_results.json / sources.json -> ops_* tables.

Turns dbt's native artifacts into two operational audit tables in the
warehouse's ``ops`` schema:

- ``ops.ops_dbt_run_audit`` — one row per node per invocation (grain:
  ``invocation_id, unique_id``), with status, timings and failure counts.
- ``ops.ops_freshness_slo`` — one row per source per freshness invocation,
  with the computed lag and the SLO verdict (``PASS`` / ``WARN`` / ``BREACH``).

SLO thresholds mirror the contract §1 freshness gates declared in
``dbt_project/models/staging/sources.yml`` (warn after 24 h, error after
48 h). Every row write is idempotent: re-parsing the same artifact (DAG task
retry, operator replay) replaces on the primary key instead of duplicating.

Exit contract for the CLI (``charging-commerce audit-dbt``):

- ``0`` — all sources ``PASS`` and no failed dbt nodes;
- ``1`` — at least one freshness ``WARN`` (still publishing, operator attention);
- ``2`` — any freshness ``BREACH`` or any failed/error dbt node (alert).

All timestamps are normalized to naive UTC before storage.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import duckdb

#: Contract §1 freshness gates (warn / error), mirrored from sources.yml.
DEFAULT_WARN_HOURS = 24.0
DEFAULT_ERROR_HOURS = 48.0

OPS_SCHEMA = "ops"
RUN_AUDIT_TABLE = "ops_dbt_run_audit"
FRESHNESS_TABLE = "ops_freshness_slo"

# dbt node statuses that count as failures (models: error; tests: fail/error).
_FAILURE_STATUSES = {"error", "fail", "failure"}


def _utc(text: str | None) -> datetime | None:
    """Parse a dbt artifact ISO timestamp to naive UTC (None passes through)."""
    if text is None:
        return None
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value


def _now_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _ensure_ops_tables(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(f"create schema if not exists {OPS_SCHEMA}")
    con.execute(
        f"""
        create table if not exists {OPS_SCHEMA}.{RUN_AUDIT_TABLE} (
            invocation_id varchar not null,
            unique_id varchar not null,
            node_name varchar,
            resource_type varchar,
            status varchar not null,
            execution_time_s double,
            failures bigint,
            started_at timestamp,
            completed_at timestamp,
            git_sha varchar,
            recorded_at timestamp not null,
            primary key (invocation_id, unique_id)
        )
        """
    )
    con.execute(
        f"""
        create table if not exists {OPS_SCHEMA}.{FRESHNESS_TABLE} (
            invocation_id varchar not null,
            source_unique_id varchar not null,
            source_name varchar,
            freshness_status varchar,
            max_loaded_at timestamp,
            snapshotted_at timestamp,
            lag_hours double,
            warn_after_hours double not null,
            error_after_hours double not null,
            slo_status varchar not null,
            alert_json varchar,
            recorded_at timestamp not null,
            primary key (invocation_id, source_unique_id)
        )
        """
    )


@dataclass(frozen=True)
class NodeResult:
    """One parsed ``run_results.json`` entry."""

    unique_id: str
    node_name: str
    resource_type: str
    status: str
    execution_time_s: float
    failures: int | None
    started_at: datetime | None
    completed_at: datetime | None


@dataclass(frozen=True)
class SourceFreshness:
    """One parsed ``sources.json`` entry."""

    unique_id: str
    source_name: str
    freshness_status: str
    max_loaded_at: datetime | None
    snapshotted_at: datetime | None


@dataclass(frozen=True)
class FreshnessVerdict:
    """SLO verdict for one source, plus the structured alert payload on WARN/BREACH."""

    verdict: SourceFreshness
    lag_hours: float | None
    slo_status: str  # PASS | WARN | BREACH
    alert: dict | None = None


@dataclass(frozen=True)
class RunAudit:
    """Summary of one ``run_results.json`` parse."""

    invocation_id: str
    dbt_version: str
    nodes: list[NodeResult] = field(default_factory=list)

    @property
    def failures(self) -> list[NodeResult]:
        return [n for n in self.nodes if n.status in _FAILURE_STATUSES]

    @property
    def failed_count(self) -> int:
        return len(self.failures)

    @property
    def total_execution_time_s(self) -> float:
        return sum(n.execution_time_s for n in self.nodes)


def parse_run_results(path: Path) -> RunAudit:
    """Parse ``run_results.json`` into a node-level summary."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    nodes: list[NodeResult] = []
    for result in payload.get("results", []):
        timing = {t.get("name"): t for t in result.get("timing", [])}
        execute = timing.get("execute") or {}
        node = result.get("node") or {}
        nodes.append(
            NodeResult(
                unique_id=result["unique_id"],
                node_name=node.get("name") or result["unique_id"],
                resource_type=node.get("resource_type") or result["unique_id"].split(".")[0],
                status=str(result.get("status", "unknown")),
                execution_time_s=float(result.get("execution_time") or 0.0),
                failures=result.get("failures"),
                started_at=_utc(execute.get("started_at")),
                completed_at=_utc(execute.get("completed_at")),
            )
        )
    return RunAudit(
        invocation_id=payload["metadata"]["invocation_id"],
        dbt_version=payload["metadata"].get("dbt_version", "unknown"),
        nodes=nodes,
    )


def parse_sources(path: Path) -> list[SourceFreshness]:
    """Parse ``sources.json`` (dbt source freshness output)."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        SourceFreshness(
            unique_id=result["unique_id"],
            source_name=result.get("name") or result["unique_id"],
            freshness_status=str(result.get("status", "unknown")),
            max_loaded_at=_utc(result.get("max_loaded_at")),
            snapshotted_at=_utc(result.get("snapshotted_at")),
        )
        for result in payload.get("results", [])
    ]


def classify_freshness(
    verdict: SourceFreshness, warn_hours: float, error_hours: float
) -> FreshnessVerdict:
    """Compute lag hours and the SLO verdict for one source row.

    The dbt-reported ``freshness_status`` participates too: a source dbt
    itself marked ``error``/``fail`` (e.g. missing relation) is a ``BREACH``
    even without a computable lag.
    """
    lag_hours: float | None = None
    if verdict.max_loaded_at is not None and verdict.snapshotted_at is not None:
        lag_seconds = (verdict.snapshotted_at - verdict.max_loaded_at).total_seconds()
        lag_hours = max(lag_seconds / 3600.0, 0.0)

    lag_breaches = lag_hours is not None and lag_hours > error_hours
    if verdict.freshness_status in _FAILURE_STATUSES or lag_breaches:
        status = "BREACH"
    elif lag_hours is not None and lag_hours > warn_hours:
        status = "WARN"
    else:
        status = "PASS"

    alert = None
    if status in {"WARN", "BREACH"}:
        alert = {
            "alert": "freshness_slo",
            "level": status,
            "source": verdict.unique_id,
            "lag_hours": round(lag_hours, 2) if lag_hours is not None else None,
            "threshold_hours": warn_hours if status == "WARN" else error_hours,
            "freshness_status": verdict.freshness_status,
        }
    return FreshnessVerdict(verdict, lag_hours, status, alert)


def audit_run_results(
    con: duckdb.DuckDBPyConnection, run_results_path: Path, git_sha: str | None = None
) -> RunAudit:
    """Upsert one ``run_results.json`` into ``ops_dbt_run_audit`` (idempotent)."""
    audit = parse_run_results(run_results_path)
    _ensure_ops_tables(con)
    recorded_at = _now_utc()
    for node in audit.nodes:
        con.execute(
            f"""
            insert or replace into {OPS_SCHEMA}.{RUN_AUDIT_TABLE}
            (invocation_id, unique_id, node_name, resource_type, status,
             execution_time_s, failures, started_at, completed_at, git_sha, recorded_at)
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                audit.invocation_id,
                node.unique_id,
                node.node_name,
                node.resource_type,
                node.status,
                node.execution_time_s,
                node.failures,
                node.started_at,
                node.completed_at,
                git_sha,
                recorded_at,
            ],
        )
    return audit


def audit_sources(
    con: duckdb.DuckDBPyConnection,
    sources_path: Path,
    warn_hours: float = DEFAULT_WARN_HOURS,
    error_hours: float = DEFAULT_ERROR_HOURS,
) -> list[FreshnessVerdict]:
    """Upsert one ``sources.json`` into ``ops_freshness_slo`` (idempotent).

    The grouping key is the artifact's own ``metadata.invocation_id`` (dbt
    writes one freshness invocation per file), so re-parsing the same file
    replaces its rows on the primary key instead of duplicating them.
    """
    payload = json.loads(Path(sources_path).read_text(encoding="utf-8"))
    invocation_id = payload.get("metadata", {}).get("invocation_id")
    if not invocation_id:
        raise SystemExit("sources.json has no metadata.invocation_id (not a dbt artifact?)")

    verdicts = [classify_freshness(v, warn_hours, error_hours) for v in parse_sources(sources_path)]
    _ensure_ops_tables(con)
    recorded_at = _now_utc()
    for v in verdicts:
        con.execute(
            f"""
            insert or replace into {OPS_SCHEMA}.{FRESHNESS_TABLE}
            (invocation_id, source_unique_id, source_name, freshness_status,
             max_loaded_at, snapshotted_at, lag_hours, warn_after_hours,
             error_after_hours, slo_status, alert_json, recorded_at)
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                invocation_id,
                v.verdict.unique_id,
                v.verdict.source_name,
                v.verdict.freshness_status,
                v.verdict.max_loaded_at,
                v.verdict.snapshotted_at,
                v.lag_hours,
                warn_hours,
                error_hours,
                v.slo_status,
                json.dumps(v.alert, sort_keys=True) if v.alert else None,
                recorded_at,
            ],
        )
    return verdicts


def audit_dbt_artifacts(
    db_path: Path,
    run_results_path: Path | None = None,
    sources_path: Path | None = None,
    warn_hours: float = DEFAULT_WARN_HOURS,
    error_hours: float = DEFAULT_ERROR_HOURS,
    git_sha: str | None = None,
) -> tuple[int, list[dict]]:
    """Full audit pass over the two artifacts; returns ``(exit_code, alerts)``.

    Missing artifacts are skipped individually (a failed freshness run still
    writes ``sources.json`` with error rows, but a crash before ``dbt build``
    leaves no ``run_results.json``). Exit codes follow the module docstring.
    """
    if not (run_results_path and Path(run_results_path).is_file()) and not (
        sources_path and Path(sources_path).is_file()
    ):
        raise SystemExit("audit-dbt: neither run_results nor sources artifact exists")

    alerts: list[dict] = []
    exit_code = 0
    con = duckdb.connect(str(db_path))
    try:
        if run_results_path and Path(run_results_path).is_file():
            audit = audit_run_results(con, run_results_path, git_sha)
            for node in audit.failures:
                alerts.append(
                    {
                        "alert": "dbt_node_failed",
                        "level": "BREACH",
                        "unique_id": node.unique_id,
                        "status": node.status,
                        "invocation_id": audit.invocation_id,
                    }
                )
            if audit.failed_count:
                exit_code = max(exit_code, 2)

        if sources_path and Path(sources_path).is_file():
            worst = 0
            for v in audit_sources(con, sources_path, warn_hours, error_hours):
                if v.alert:
                    alerts.append(v.alert)
                if v.slo_status == "BREACH":
                    worst = 2
                elif v.slo_status == "WARN":
                    worst = max(worst, 1)
            exit_code = max(exit_code, worst)
    finally:
        con.close()
    return exit_code, alerts


def git_sha_from_env() -> str | None:
    """GIT_SHA env passthrough (CI stamps it; local runs leave it null)."""
    return os.environ.get("GIT_SHA") or None
