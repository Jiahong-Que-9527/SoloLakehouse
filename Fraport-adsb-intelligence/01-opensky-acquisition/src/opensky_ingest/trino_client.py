"""Bounded query helper for the OpenSky Trino service."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .errors import AuthRequired, SourceError

QUEUE_MARKERS = ("QUERY_QUEUE_FULL", "EXCEEDED_GLOBAL_MEMORY_LIMIT", "CLUSTER_OUT_OF_MEMORY")
SCAN_MARKERS = ("Exceeded scan limit",)


@dataclass
class QueryInfo:
    query_id: str | None
    columns: list[str]
    rows: int
    elapsed_seconds: float
    processed_bytes: int | None
    stats: dict[str, Any] = field(default_factory=dict)


def classify_error(exc: BaseException) -> Exception:
    """Map a client exception to a stable, log-safe error class.

    The raw message is not copied into the result: Trino authentication errors
    may contain login URLs.
    """
    if isinstance(exc, (AuthRequired, SourceError)):
        return exc
    name = type(exc).__name__
    text = str(exc)
    if name == "TrinoAuthError":
        return AuthRequired("AUTH_REQUIRED: renew the OpenSky session with `login`")
    if any(marker in text for marker in SCAN_MARKERS):
        return SourceError("SCAN_LIMIT_EXCEEDED")
    if any(marker in text for marker in QUEUE_MARKERS) or "queue" in text.lower():
        return SourceError("SOURCE_BUSY")
    if isinstance(exc, TimeoutError) or "timeout" in text.lower() or "cancel" in text.lower():
        return SourceError("QUERY_TIMEOUT")
    return SourceError("QUERY_FAILED", name)


def run_query(
    connection: Any,
    sql: str,
    consume: Callable[[tuple], None] | None = None,
    *,
    timeout: int = 300,
) -> QueryInfo:
    """Run one query, stream rows to `consume`, cancel it after `timeout` seconds."""
    cursor = connection.cursor()
    timer = threading.Timer(timeout, cursor.cancel)
    timer.daemon = True
    started = time.monotonic()
    count = 0
    try:
        timer.start()
        cursor.execute(sql)
        columns = [d[0] for d in (cursor.description or [])]
        for row in cursor:
            count += 1
            if consume is not None:
                consume(tuple(row))
        stats = dict(cursor.stats or {})
        return QueryInfo(
            query_id=cursor.query_id,
            columns=columns,
            rows=count,
            elapsed_seconds=time.monotonic() - started,
            processed_bytes=stats.get("processedBytes"),
            stats=stats,
        )
    except BaseException as exc:
        try:
            cursor.cancel()
        except Exception:  # noqa: BLE001 - cancellation must not hide the original error
            pass
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        raise classify_error(exc) from None
    finally:
        timer.cancel()
        try:
            cursor.close()
        except Exception:  # noqa: BLE001
            pass


def fetch_all(
    connection: Any, sql: str, *, timeout: int = 300, max_rows: int = 10_000
) -> tuple[list[tuple], QueryInfo]:
    """Run a small query and return all rows. Refuses large results."""
    rows: list[tuple] = []

    def consume(row: tuple) -> None:
        if len(rows) >= max_rows:
            raise SourceError("RESULT_TOO_LARGE")
        rows.append(row)

    info = run_query(connection, sql, consume, timeout=timeout)
    return rows, info
