"""Report Freshness Service: flag stale meter snapshots.

Reads one configured snapshot document from a read-only path, validates it,
and reports its age against a configurable maximum. A stale snapshot is a
valid data-quality answer served with HTTP 200; a missing, unreadable or
invalid snapshot answers with a structured availability error. /metrics
serves request counters, latency and a freshness gauge so callers can
separate a stale-snapshot signal from an availability incident.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from freshness import __version__

SNAPSHOT_PATH_ENV = "FRESHNESS_SNAPSHOT_PATH"
MAX_AGE_ENV = "MAX_AGE_HOURS"
NOW_ENV = "FRESHNESS_NOW"  # deterministic clock override for tests

_UNAVAILABLE_CODES = {"not_configured", "unreadable"}
SUPPORTED_SCHEMA_VERSION = 1

REQUESTS = Counter("http_requests_total", "HTTP requests processed", ["route", "code"])
LATENCY = Histogram("http_request_duration_seconds", "Request latency in seconds", ["route"])
FRESHNESS = Gauge(
    "snapshot_freshness", "1 fresh, 0 stale or unavailable", ["snapshot_id"]
)

app = FastAPI(title="Report Freshness Service", version=__version__)


class SnapshotError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _public_code(exc: SnapshotError) -> str:
    return "snapshot_unavailable" if exc.code in _UNAVAILABLE_CODES else "snapshot_invalid"


def _availability_error(code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=503, content={"error": {"code": code, "message": message}}
    )


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise SnapshotError(code, message)


def _now() -> datetime:
    override = os.environ.get(NOW_ENV, "").strip()
    if override:
        return datetime.fromisoformat(override.replace("Z", "+00:00"))
    return datetime.now(timezone.utc)


def _load_snapshot() -> dict[str, Any]:
    path = os.environ.get(SNAPSHOT_PATH_ENV, "").strip()
    _require(bool(path), "not_configured", "No snapshot is configured.")
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        raise SnapshotError(
            "unreadable", "The configured snapshot is missing or unreadable."
        ) from exc
    try:
        document = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SnapshotError("malformed", "The snapshot is not valid JSON.") from exc
    _require(isinstance(document, dict), "malformed", "The snapshot must be a JSON object.")

    required = ("schema_version", "snapshot_id", "snapshot_generated_at")
    missing = [field for field in required if field not in document]
    _require(
        not missing,
        "missing_field",
        f"Missing required field(s): {', '.join(sorted(missing))}.",
    )
    _require(
        isinstance(document["schema_version"], int)
        and not isinstance(document["schema_version"], bool)
        and document["schema_version"] == SUPPORTED_SCHEMA_VERSION,
        "unsupported_schema_version",
        f"Unsupported schema version; supported version is {SUPPORTED_SCHEMA_VERSION}.",
    )
    _require(
        isinstance(document["snapshot_id"], str) and document["snapshot_id"].strip() != "",
        "invalid_field",
        "snapshot_id must be a non-empty string.",
    )
    _require(
        isinstance(document["snapshot_generated_at"], str),
        "invalid_field",
        "snapshot_generated_at must be a UTC timestamp string.",
    )
    try:
        generated = datetime.fromisoformat(
            document["snapshot_generated_at"].replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise SnapshotError(
            "invalid_field", "snapshot_generated_at must be a UTC timestamp string."
        ) from exc
    _require(
        generated.tzinfo is not None,
        "invalid_field",
        "snapshot_generated_at must carry a UTC offset.",
    )
    generated = generated.astimezone(timezone.utc)

    try:
        max_age = float(os.environ.get(MAX_AGE_ENV, "24"))
    except ValueError as exc:
        raise SnapshotError("invalid_config", "MAX_AGE_HOURS must be a number.") from exc
    _require(max_age > 0, "invalid_config", "MAX_AGE_HOURS must be positive.")

    age_hours = max(0.0, (_now() - generated).total_seconds() / 3600.0)
    verdict = "fresh" if age_hours <= max_age else "stale"
    return {
        "schema_version": SUPPORTED_SCHEMA_VERSION,
        "snapshot_id": document["snapshot_id"],
        "snapshot_generated_at": generated.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "age_hours": round(age_hours, 2),
        "max_age_hours": max_age,
        "verdict": verdict,
    }


@app.middleware("http")
async def instrument(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    route = request.url.path
    REQUESTS.labels(route, str(response.status_code)).inc()
    LATENCY.labels(route).observe(time.perf_counter() - start)
    return response


@app.get("/live")
def live() -> dict[str, str]:
    return {"status": "live"}


@app.get("/ready")
def ready() -> JSONResponse:
    try:
        snapshot = _load_snapshot()
    except SnapshotError as exc:
        FRESHNESS.labels("unavailable").set(0)
        return _availability_error(_public_code(exc), exc.message)
    FRESHNESS.labels(snapshot["snapshot_id"]).set(
        1 if snapshot["verdict"] == "fresh" else 0
    )
    return JSONResponse(status_code=200, content={"status": "ready"})


@app.get("/v1/freshness/latest")
def freshness_latest() -> JSONResponse:
    try:
        snapshot = _load_snapshot()
    except SnapshotError as exc:
        FRESHNESS.labels("unavailable").set(0)
        return _availability_error(_public_code(exc), exc.message)
    FRESHNESS.labels(snapshot["snapshot_id"]).set(
        1 if snapshot["verdict"] == "fresh" else 0
    )
    return JSONResponse(status_code=200, content=snapshot)


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
