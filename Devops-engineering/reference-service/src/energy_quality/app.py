"""FastAPI application exposing the configured audit report.

Liveness reports whether the application can respond. Readiness and the
quality route report whether the configured report can be interpreted.
A valid report with a failed coverage result stays readable and is served
with HTTP 200. Missing, unreadable or invalid input answers with a
structured availability error that omits filesystem details.

/metrics serves Prometheus signals: request count and latency per route,
plus a gauge for the configured audit's coverage result so callers can
separate a data-quality change from an availability incident.
"""

from __future__ import annotations

import os
import time
from typing import Any

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from energy_quality.report import ReportError, parse_report

REPORT_PATH_ENV = "AUDIT_REPORT_PATH"

_UNAVAILABLE_CODES = {"not_configured", "unreadable"}

REQUESTS = Counter("http_requests_total", "HTTP requests processed", ["route", "code"])
LATENCY = Histogram("http_request_duration_seconds", "Request latency in seconds", ["route"])
AUDIT_QUALITY = Gauge(
    "audit_coverage_result",
    "1 when the configured audit passed, 0 when it failed or is unavailable",
    ["report_id"],
)

app = FastAPI(title="Energy Data Quality Service", version="0.2.0")


@app.middleware("http")
async def instrument(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    route = request.url.path
    REQUESTS.labels(route, str(response.status_code)).inc()
    LATENCY.labels(route).observe(time.perf_counter() - start)
    return response


def _availability_error(code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=503, content={"error": {"code": code, "message": message}})


def _public_code(exc: ReportError) -> str:
    return "report_unavailable" if exc.code in _UNAVAILABLE_CODES else "report_invalid"


def _load_report() -> dict[str, Any]:
    """Read and parse the configured report; raise ReportError when unusable."""
    path = os.environ.get(REPORT_PATH_ENV, "").strip()
    if not path:
        raise ReportError("not_configured", "No audit report is configured.")
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        raise ReportError(
            "unreadable", "The configured audit report is missing or unreadable."
        ) from exc
    return parse_report(data)


@app.get("/live")
def live() -> dict[str, str]:
    return {"status": "live"}


@app.get("/ready")
def ready() -> JSONResponse:
    try:
        report = _load_report()
    except ReportError as exc:
        AUDIT_QUALITY.labels("unavailable").set(0)
        return _availability_error(_public_code(exc), exc.message)
    AUDIT_QUALITY.labels(report["report_id"]).set(1 if report["coverage_result"] == "passed" else 0)
    return JSONResponse(status_code=200, content={"status": "ready"})


@app.get("/v1/quality/latest")
def quality_latest() -> JSONResponse:
    try:
        report = _load_report()
    except ReportError as exc:
        AUDIT_QUALITY.labels("unavailable").set(0)
        return _availability_error(_public_code(exc), exc.message)
    AUDIT_QUALITY.labels(report["report_id"]).set(1 if report["coverage_result"] == "passed" else 0)
    return JSONResponse(status_code=200, content=report)


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
