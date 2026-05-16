"""Trino HTTP client helpers for Hive staging tables and Iceberg Gold refresh."""

from __future__ import annotations

import time
from typing import Any

import requests
import structlog

from runtime_identity import get_trino_user
from storage_config import default_warehouse_uri

logger = structlog.get_logger()

ICEBERG_GOLD_TABLE = "iceberg.gold.ecb_dax_features_iceberg"


def execute_trino_sql(
    trino_url: str,
    sql: str,
    *,
    catalog: str | None = None,
    schema: str | None = None,
    user: str | None = None,
    poll_timeout_s: float = 180.0,
) -> dict[str, Any]:
    """Run a SQL statement via Trino REST API and poll until completion."""
    base = trino_url.rstrip("/")
    headers: dict[str, str] = {
        "X-Trino-User": user or get_trino_user(),
        "Content-Type": "text/plain; charset=utf-8",
    }
    if catalog:
        headers["X-Trino-Catalog"] = catalog
    if schema:
        headers["X-Trino-Schema"] = schema

    response = requests.post(
        f"{base}/v1/statement",
        data=sql.encode("utf-8"),
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    payload: dict[str, Any] = response.json()

    deadline = time.monotonic() + poll_timeout_s
    while True:
        if "error" in payload:
            message = payload["error"].get("message", "unknown Trino error")
            raise ValueError(message)
        next_uri = payload.get("nextUri")
        if not next_uri:
            return payload
        if time.monotonic() > deadline:
            raise TimeoutError("Trino query polling exceeded timeout")
        response = requests.get(next_uri, timeout=30)
        response.raise_for_status()
        payload = response.json()


def register_hive_gold_staging_parquet(trino_url: str, bucket: str) -> None:
    """Hive external table over the Gold Parquet folder (staging for Iceberg CTAS)."""
    execute_trino_sql(
        trino_url,
        f"CREATE SCHEMA IF NOT EXISTS hive.gold WITH (location = 's3://{bucket}/gold/')",
    )
    execute_trino_sql(
        trino_url,
        f"""
        CREATE TABLE IF NOT EXISTS hive.gold.ecb_dax_features (
            event_date DATE,
            rate_change_bps DOUBLE,
            rate_level_pct DOUBLE,
            is_rate_hike BOOLEAN,
            is_rate_cut BOOLEAN,
            dax_pre_close DOUBLE,
            dax_return_1d DOUBLE,
            dax_return_5d DOUBLE,
            dax_volatility_pre_5d DOUBLE
        )
        WITH (
            format = 'PARQUET',
            external_location = 's3://{bucket}/gold/rate_impact_features/'
        )
        """.strip(),
    )
    logger.info("hive_gold_staging_registered", bucket=bucket)


def _join_uri(base_uri: str, suffix: str) -> str:
    return f"{base_uri.rstrip('/')}/{suffix.lstrip('/')}"


def refresh_iceberg_gold_from_hive(
    trino_url: str,
    bucket: str,
    warehouse_uri: str | None = None,
) -> None:
    """Replace Iceberg Gold table from Hive staging Parquet (CTAS)."""
    effective_warehouse_uri = warehouse_uri or default_warehouse_uri(bucket)
    iceberg_gold_location = _join_uri(effective_warehouse_uri, "gold/")
    execute_trino_sql(
        trino_url,
        f"CREATE SCHEMA IF NOT EXISTS iceberg.gold WITH (location = '{iceberg_gold_location}')",
    )
    execute_trino_sql(trino_url, f"DROP TABLE IF EXISTS {ICEBERG_GOLD_TABLE}")
    execute_trino_sql(
        trino_url,
        """
        CREATE TABLE iceberg.gold.ecb_dax_features_iceberg
        AS SELECT * FROM hive.gold.ecb_dax_features
        """,
    )
    logger.info(
        "iceberg_gold_refreshed",
        bucket=bucket,
        warehouse_uri=effective_warehouse_uri,
        table=ICEBERG_GOLD_TABLE,
    )


def register_gold_tables_trino(
    trino_url: str,
    bucket: str,
    warehouse_uri: str | None = None,
) -> None:
    """Ensure Hive staging + Iceberg Gold are aligned after Parquet write."""
    attempts = 3
    delay_s = 5.0
    for attempt in range(1, attempts + 1):
        try:
            register_hive_gold_staging_parquet(trino_url, bucket)
            refresh_iceberg_gold_from_hive(trino_url, bucket, warehouse_uri=warehouse_uri)
            return
        except (requests.RequestException, TimeoutError, ValueError) as exc:
            if attempt >= attempts or not _is_retryable_trino_error(exc):
                raise
            logger.warning(
                "trino_gold_registration_retry",
                attempt=attempt,
                max_attempts=attempts,
                error=str(exc),
            )
            time.sleep(delay_s)


def _is_retryable_trino_error(exc: Exception) -> bool:
    message = str(exc).lower()
    transient_markers = (
        "sockettimeoutexception",
        "read timed out",
        "timeout",
        "timed out",
        "hive-metastore",
    )
    return any(marker in message for marker in transient_markers)
