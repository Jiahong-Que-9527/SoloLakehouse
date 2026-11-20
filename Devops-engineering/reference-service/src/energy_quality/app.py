"""FastAPI application exposing the configured audit report.

Liveness reports whether the application can respond. Readiness and the
quality route report whether the configured report can be interpreted.
A valid report with a failed coverage result stays readable and is served
with HTTP 200. Missing, unreadable or invalid input answers with a
structured availability error that omits filesystem details.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from energy_quality.report import ReportError, parse_report

REPORT_PATH_ENV = "AUDIT_REPORT_PATH"

_UNAVAILABLE_CODES = {"not_configured", "unreadable"}

app = FastAPI(title="Energy Data Quality Service", version="0.1.0")


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
        _load_report()
    except ReportError as exc:
        return _availability_error(_public_code(exc), exc.message)
    return JSONResponse(status_code=200, content={"status": "ready"})


@app.get("/v1/quality/latest")
def quality_latest() -> JSONResponse:
    try:
        report = _load_report()
    except ReportError as exc:
        return _availability_error(_public_code(exc), exc.message)
    return JSONResponse(status_code=200, content=report)
