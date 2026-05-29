"""Trino HTTP client helper for ad-hoc SQL execution.

Hive staging and CTAS flows were removed when all layers migrated to Iceberg
(written via pyiceberg directly).  This module now only exposes the generic
`execute_trino_sql` utility, kept for operational queries (e.g. ANALYZE,
CALL system.sync_partition_metadata, future DDL helpers).
"""

from __future__ import annotations

import time
from typing import Any

import requests
import structlog

from runtime_identity import get_trino_user

logger = structlog.get_logger()


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
