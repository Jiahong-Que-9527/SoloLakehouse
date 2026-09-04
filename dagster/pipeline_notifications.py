"""Email notifications when governed Dagster pipeline jobs finish."""

from __future__ import annotations

import os
import smtplib
import ssl
import urllib.parse
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Any, Mapping

import requests
import structlog
import trino

from dagster import (
    DagsterRunStatus,
    DefaultSensorStatus,
    RunStatusSensorContext,
    SkipReason,
    run_status_sensor,
)
from runtime_identity import get_trino_user

logger = structlog.get_logger()

PIPELINE_JOB_NAMES = frozenset({"demo_data_flow_job", "full_pipeline_job"})

PIPELINE_ICEBERG_TABLES: tuple[tuple[str, str, str], ...] = (
    ("bronze", "ecb_rates", "observation_date"),
    ("bronze", "german_equity_proxy_daily", "observation_date"),
    ("silver", "ecb_rates_cleaned", "observation_date"),
    ("silver", "german_equity_proxy_daily_cleaned", "observation_date"),
    ("gold", "ecb_german_equity_proxy_features", "event_date"),
)

_DAGSTER_RUN_QUERY = """
query PipelineNotifyRun($runId: ID!) {
  runOrError(runId: $runId) {
    __typename
    ... on Run {
      runId
      status
      jobName
      startTime
      endTime
      assetMaterializations {
        assetKey { path }
        metadataEntries {
          label
          ... on TextMetadataEntry { text }
          ... on IntMetadataEntry { intValue }
          ... on FloatMetadataEntry { floatValue }
        }
      }
    }
  }
}
"""


@dataclass(frozen=True)
class SmtpNotificationConfig:
    """SMTP settings for pipeline completion emails."""

    to_addresses: tuple[str, ...]
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    from_address: str
    use_tls: bool


@dataclass(frozen=True)
class AssetMaterializationSummary:
    """One materialized asset and selected Dagster metadata."""

    asset_key: str
    metadata: dict[str, str]


@dataclass(frozen=True)
class TableSummary:
    """Row count and date range for one Iceberg table."""

    qualified_name: str
    row_count: int
    min_date: str | None
    max_date: str | None
    error: str | None = None


@dataclass(frozen=True)
class PipelineRunSummary:
    """Run context and data snapshot for one pipeline notification."""

    job_name: str
    run_id: str
    status_label: str
    dagster_url: str
    start_time: str | None = None
    end_time: str | None = None
    materializations: tuple[AssetMaterializationSummary, ...] = ()
    table_summaries: tuple[TableSummary, ...] = ()
    run_lookup_error: str | None = None
    table_lookup_error: str | None = None


def parse_recipient_addresses(raw_value: str) -> tuple[str, ...]:
    """Parse comma-separated recipient emails."""
    return tuple(address.strip() for address in raw_value.split(",") if address.strip())


def notification_config_from_environ(
    environ: Mapping[str, str] | None = None,
) -> SmtpNotificationConfig | None:
    """Return SMTP config when PIPELINE_NOTIFY_EMAIL_TO and SMTP_HOST are set."""
    env = os.environ if environ is None else environ
    to_addresses = parse_recipient_addresses(env.get("PIPELINE_NOTIFY_EMAIL_TO", ""))
    smtp_host = env.get("SMTP_HOST", "").strip()
    if not to_addresses or not smtp_host:
        return None

    smtp_user = env.get("SMTP_USER", "").strip()
    smtp_password = env.get("SMTP_PASSWORD", "")
    from_address = env.get("SMTP_FROM", "").strip() or smtp_user or to_addresses[0]
    port_raw = env.get("SMTP_PORT", "587").strip()
    use_tls = env.get("SMTP_USE_TLS", "true").strip().lower() not in {"0", "false", "no"}

    return SmtpNotificationConfig(
        to_addresses=to_addresses,
        smtp_host=smtp_host,
        smtp_port=int(port_raw),
        smtp_user=smtp_user,
        smtp_password=smtp_password,
        from_address=from_address,
        use_tls=use_tls,
    )


def _format_timestamp(epoch: object) -> str | None:
    if epoch is None:
        return None
    if not isinstance(epoch, (int, float, str)):
        return str(epoch)
    try:
        return datetime.fromtimestamp(float(epoch), tz=UTC).isoformat()
    except (TypeError, ValueError):
        return str(epoch)


def _metadata_map(entries: object) -> dict[str, str]:
    metadata: dict[str, str] = {}
    if not isinstance(entries, list):
        return metadata
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        label = entry.get("label")
        if not isinstance(label, str) or not label:
            continue
        if "text" in entry and entry["text"] is not None:
            metadata[label] = str(entry["text"])
        elif "intValue" in entry and entry["intValue"] is not None:
            metadata[label] = str(entry["intValue"])
        elif "floatValue" in entry and entry["floatValue"] is not None:
            metadata[label] = str(entry["floatValue"])
    return metadata


def _asset_key_from_materialization(materialization: dict[str, Any]) -> str | None:
    asset = materialization.get("assetKey")
    path = asset.get("path") if isinstance(asset, dict) else None
    if not isinstance(path, list) or not path or not all(isinstance(part, str) for part in path):
        return None
    return "/".join(path)


def fetch_run_materializations(
    dagster_url: str,
    run_id: str,
    *,
    session: requests.Session | None = None,
    timeout_seconds: float = 15,
) -> tuple[dict[str, Any] | None, str | None]:
    """Load Dagster run details and materializations through GraphQL."""
    client = session or requests.Session()
    try:
        response = client.post(
            f"{dagster_url.rstrip('/')}/graphql",
            json={"query": _DAGSTER_RUN_QUERY, "variables": {"runId": run_id}},
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        return None, f"Dagster GraphQL request failed: {exc}"
    except (TypeError, ValueError) as exc:
        return None, f"Dagster GraphQL response is not valid JSON: {exc}"

    if not isinstance(payload, dict):
        return None, "Dagster GraphQL response must be an object"
    errors = payload.get("errors")
    if errors:
        return None, f"Dagster GraphQL returned errors: {errors!r}"

    data = payload.get("data")
    if not isinstance(data, dict):
        return None, "Dagster GraphQL response has no data payload"
    run = data.get("runOrError")
    if not isinstance(run, dict) or run.get("__typename") != "Run":
        return None, "Dagster run lookup did not return a Run object"
    if run.get("runId") != run_id:
        return None, "Dagster run lookup returned a different run id"
    return run, None


def materializations_from_run(run: dict[str, Any]) -> tuple[AssetMaterializationSummary, ...]:
    """Extract asset materialization summaries from one Dagster run payload."""
    raw_materializations = run.get("assetMaterializations")
    if not isinstance(raw_materializations, list):
        return ()

    summaries: list[AssetMaterializationSummary] = []
    for materialization in raw_materializations:
        if not isinstance(materialization, dict):
            continue
        asset_key = _asset_key_from_materialization(materialization)
        if asset_key is None:
            continue
        summaries.append(
            AssetMaterializationSummary(
                asset_key=asset_key,
                metadata=_metadata_map(materialization.get("metadataEntries")),
            )
        )
    return tuple(summaries)


def query_table_summary(
    trino_url: str,
    *,
    schema: str,
    table: str,
    date_column: str,
    trino_user: str | None = None,
) -> TableSummary:
    """Return row count and date range for one Iceberg table."""
    qualified_name = f"iceberg.{schema}.{table}"
    sql = (
        f"SELECT count(*) AS row_count, "
        f"cast(min({date_column}) AS varchar) AS min_date, "
        f"cast(max({date_column}) AS varchar) AS max_date "
        f"FROM {qualified_name}"
    )
    parsed = urllib.parse.urlparse(trino_url)
    conn = trino.dbapi.connect(
        host=parsed.hostname or "localhost",
        port=parsed.port or 8080,
        user=trino_user or get_trino_user(),
        http_scheme=parsed.scheme or "http",
    )
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        row = cursor.fetchone()
        if row is None:
            return TableSummary(qualified_name, 0, None, None, error="Trino returned no rows")
        return TableSummary(
            qualified_name=qualified_name,
            row_count=int(row[0]),
            min_date=str(row[1]) if row[1] is not None else None,
            max_date=str(row[2]) if row[2] is not None else None,
        )
    except Exception as exc:
        return TableSummary(qualified_name, 0, None, None, error=str(exc))
    finally:
        conn.close()


def fetch_pipeline_table_summaries(
    trino_url: str,
    *,
    trino_user: str | None = None,
) -> tuple[TableSummary, ...]:
    """Query Trino for current pipeline table stats."""
    return tuple(
        query_table_summary(
            trino_url,
            schema=schema,
            table=table,
            date_column=date_column,
            trino_user=trino_user,
        )
        for schema, table, date_column in PIPELINE_ICEBERG_TABLES
    )


def build_pipeline_run_summary(
    *,
    job_name: str,
    run_id: str,
    status_label: str,
    dagster_url: str,
    trino_url: str | None = None,
    include_table_summaries: bool = True,
) -> PipelineRunSummary:
    """Collect run metadata and current Iceberg table stats for one notification."""
    run, run_lookup_error = fetch_run_materializations(dagster_url, run_id)
    materializations: tuple[AssetMaterializationSummary, ...] = ()
    start_time: str | None = None
    end_time: str | None = None
    if run is not None:
        materializations = materializations_from_run(run)
        start_time = _format_timestamp(run.get("startTime"))
        end_time = _format_timestamp(run.get("endTime"))

    table_summaries: tuple[TableSummary, ...] = ()
    table_lookup_error: str | None = None
    if include_table_summaries:
        effective_trino_url = trino_url or os.environ.get("TRINO_URL", "http://trino:8080")
        try:
            table_summaries = fetch_pipeline_table_summaries(effective_trino_url)
        except Exception as exc:
            table_lookup_error = str(exc)

    return PipelineRunSummary(
        job_name=job_name,
        run_id=run_id,
        status_label=status_label,
        dagster_url=dagster_url,
        start_time=start_time,
        end_time=end_time,
        materializations=materializations,
        table_summaries=table_summaries,
        run_lookup_error=run_lookup_error,
        table_lookup_error=table_lookup_error,
    )


def format_pipeline_run_email_body(summary: PipelineRunSummary) -> str:
    """Render a plain-text email body for one pipeline run."""
    run_url = f"{summary.dagster_url.rstrip('/')}/runs/{summary.run_id}"
    lines = [
        "FinLakehouse pipeline notification",
        "",
        "== Run ==",
        f"Job: {summary.job_name}",
        f"Status: {summary.status_label}",
        f"Run ID: {summary.run_id}",
        f"Started (UTC): {summary.start_time or 'n/a'}",
        f"Ended (UTC): {summary.end_time or 'n/a'}",
        f"Dagster UI: {run_url}",
    ]

    if summary.run_lookup_error:
        lines.extend(["", "== Run metadata =="])
        lines.append(f"Could not load Dagster run details: {summary.run_lookup_error}")
    elif summary.materializations:
        lines.extend(["", "== Materialized assets =="])
        for materialization in summary.materializations:
            lines.append(f"- {materialization.asset_key}")
            for key in (
                "status",
                "valid_count",
                "rejected_count",
                "row_count",
                "event_count",
                "table",
                "partition_date",
                "iceberg_snapshot_id",
            ):
                if key in materialization.metadata:
                    lines.append(f"    {key}: {materialization.metadata[key]}")
    else:
        lines.extend(
            ["", "== Materialized assets ==", "No asset materializations recorded for this run."]
        )

    if summary.table_lookup_error:
        lines.extend(["", "== Iceberg tables =="])
        lines.append(f"Could not query Trino: {summary.table_lookup_error}")
    elif summary.table_summaries:
        lines.extend(["", "== Iceberg tables (current Trino snapshot) =="])
        for table in summary.table_summaries:
            lines.append(f"- {table.qualified_name}")
            if table.error:
                lines.append(f"    error: {table.error}")
                continue
            lines.append(f"    rows: {table.row_count}")
            if table.min_date or table.max_date:
                lines.append(
                    f"    date range: {table.min_date or 'n/a'} .. {table.max_date or 'n/a'}"
                )

    return "\n".join(lines)


def build_pipeline_run_email(
    *,
    job_name: str,
    run_id: str,
    status_label: str,
    dagster_url: str,
    body: str | None = None,
) -> EmailMessage:
    """Build a plain-text completion email for one Dagster job run."""
    message = EmailMessage()
    message["Subject"] = f"[FinLakehouse] {job_name} {status_label}"
    if body is None:
        body = format_pipeline_run_email_body(
            PipelineRunSummary(
                job_name=job_name,
                run_id=run_id,
                status_label=status_label,
                dagster_url=dagster_url,
            )
        )
    message.set_content(body)
    return message


def send_pipeline_run_email(
    config: SmtpNotificationConfig,
    *,
    summary: PipelineRunSummary,
) -> None:
    """Send one pipeline completion email via SMTP."""
    message = build_pipeline_run_email(
        job_name=summary.job_name,
        run_id=summary.run_id,
        status_label=summary.status_label,
        dagster_url=summary.dagster_url,
        body=format_pipeline_run_email_body(summary),
    )
    message["From"] = config.from_address
    message["To"] = ", ".join(config.to_addresses)

    if config.use_tls:
        with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30) as client:
            client.ehlo()
            client.starttls(context=ssl.create_default_context())
            client.ehlo()
            if config.smtp_user:
                client.login(config.smtp_user, config.smtp_password)
            client.send_message(message)
        return

    with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30) as client:
        if config.smtp_user:
            client.login(config.smtp_user, config.smtp_password)
        client.send_message(message)


def _pipeline_run_email_sensor(context: RunStatusSensorContext, status_label: str):
    """Shared handler for success/failure pipeline email sensors."""
    run = context.dagster_run
    if run.job_name not in PIPELINE_JOB_NAMES:
        yield SkipReason(f"skip email for non-pipeline job: {run.job_name}")
        return

    config = notification_config_from_environ()
    if config is None:
        yield SkipReason("pipeline email disabled: set PIPELINE_NOTIFY_EMAIL_TO and SMTP_HOST")
        return

    dagster_url = os.environ.get("DAGSTER_URL", "http://dagster-webserver:3000")
    summary = build_pipeline_run_summary(
        job_name=run.job_name or "unknown_job",
        run_id=run.run_id,
        status_label=status_label,
        dagster_url=dagster_url,
        include_table_summaries=status_label == "SUCCESS",
    )
    try:
        send_pipeline_run_email(config, summary=summary)
    except Exception as exc:
        logger.error(
            "pipeline_email_failed",
            job_name=run.job_name,
            run_id=run.run_id,
            status=status_label,
            error=str(exc),
        )
        yield SkipReason(f"pipeline email failed: {exc}")
        return

    logger.info(
        "pipeline_email_sent",
        job_name=run.job_name,
        run_id=run.run_id,
        status=status_label,
        to_addresses=config.to_addresses,
    )
    yield SkipReason(f"sent {status_label} email for {run.job_name} ({run.run_id})")


@run_status_sensor(
    run_status=DagsterRunStatus.SUCCESS,
    minimum_interval_seconds=30,
    name="pipeline_success_email_sensor",
    default_status=DefaultSensorStatus.RUNNING,
    monitor_all_code_locations=True,
)
def pipeline_success_email_sensor(context: RunStatusSensorContext):
    """Email when a pipeline job run succeeds."""
    yield from _pipeline_run_email_sensor(context, "SUCCESS")


@run_status_sensor(
    run_status=DagsterRunStatus.FAILURE,
    minimum_interval_seconds=30,
    name="pipeline_failure_email_sensor",
    default_status=DefaultSensorStatus.RUNNING,
    monitor_all_code_locations=True,
)
def pipeline_failure_email_sensor(context: RunStatusSensorContext):
    """Email when a pipeline job run fails."""
    yield from _pipeline_run_email_sensor(context, "FAILURE")
