"""Trino HTTP client helpers for Hive staging tables and Iceberg Gold refresh."""

from __future__ import annotations

import os
import time
from typing import Any

import requests
import structlog

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
        "X-Trino-User": user or os.environ.get("TRINO_USER", "sololakehouse"),
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


def refresh_iceberg_gold_from_hive(trino_url: str, bucket: str) -> None:
    """Replace Iceberg Gold table from Hive staging Parquet (CTAS)."""
    execute_trino_sql(
        trino_url,
        f"CREATE SCHEMA IF NOT EXISTS iceberg.gold WITH (location = 's3://{bucket}/gold/iceberg/')",
    )
    execute_trino_sql(trino_url, f"DROP TABLE IF EXISTS {ICEBERG_GOLD_TABLE}")
    execute_trino_sql(
        trino_url,
        """
        CREATE TABLE iceberg.gold.ecb_dax_features_iceberg
        AS SELECT * FROM hive.gold.ecb_dax_features
        """,
    )
    logger.info("iceberg_gold_refreshed", bucket=bucket, table=ICEBERG_GOLD_TABLE)


def register_gold_tables_trino(trino_url: str, bucket: str) -> None:
    """Ensure Hive staging + Iceberg Gold are aligned after Parquet write."""
    register_hive_gold_staging_parquet(trino_url, bucket)
    refresh_iceberg_gold_from_hive(trino_url, bucket)
