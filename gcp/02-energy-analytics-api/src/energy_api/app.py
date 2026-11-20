"""The frozen HTTP contract (design §4) over an injected QueryPort.

Error mapping: ValidationError codes invalid_parameters / invalid_range /
query_rejected are HTTP 400; metric_not_published is HTTP 404. Every
response carries X-Request-Id, every error body is exactly
{"code", "message", "request_id"}. The caller's token is never logged.

Release semantics: without an explicit release_id the port resolves the
latest passed release. An explicit release_id whose fetch returns zero
rows is answered 404 metric_not_published — the port has no
exists(release) probe, and in this data model a published release has
rows (as-built ruling, plan Task 1.4).
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from energy_api.guards import QueryGuard, ValidationError, validate_request
from energy_api.model import Observation
from energy_api.query import QueryPort

logger = logging.getLogger("energy_api")

From = Annotated[str, Query(alias="from")]
To = Annotated[str, Query(alias="to")]
ReleaseId = Annotated[str | None, Query()]

_METRIC_ALIASES = {
    "prices": "price",
    "generation-mix": "generation_mix",
}


def _rfc3339(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _observation_json(obs: Observation) -> dict:
    return {
        "interval_start": _rfc3339(obs.interval_start),
        "interval_end": _rfc3339(obs.interval_end),
        "area": obs.area,
        "metric": obs.metric,
        "value": obs.value,
        "unit": obs.unit,
        "release_id": obs.release_id,
    }


def create_app(query: QueryPort, guard: QueryGuard | None = None) -> FastAPI:
    """Build one app instance around one data surface; tests inject the fake."""
    app = FastAPI(title="Energy Analytics API")
    active_guard = guard or QueryGuard()

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        return response

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        status = 404 if exc.code == "metric_not_published" else 400
        logger.info(
            "route=%s code=%s status=%s request_id=%s",
            request.url.path,
            exc.code,
            status,
            request.state.request_id,
        )
        return JSONResponse(
            status_code=status,
            content={
                "code": exc.code,
                "message": exc.message,
                "request_id": request.state.request_id,
            },
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    def _resolve_or_404(metric: str, release_id: str | None) -> str:
        resolved = release_id or query.resolve_release(metric)
        if resolved is None:
            message = f"metric '{metric}' has no published release"
            raise ValidationError(code="metric_not_published", message=message)
        return resolved

    def _rows_or_404(
        metric: str,
        area: str,
        start: datetime,
        end: datetime,
        release_id: str,
        explicit: bool,
    ) -> list[Observation]:
        rows = query.fetch_observations(metric, area, start, end, release_id)
        if not rows and explicit:
            message = f"release '{release_id}' is not published"
            raise ValidationError(code="metric_not_published", message=message)
        return rows

    def _metrics(
        request: Request, metric: str, area: str, from_s: str, to_s: str, release_id: str | None
    ) -> JSONResponse:
        _, name, start, end = validate_request(area, metric, from_s, to_s, active_guard)
        resolved = _resolve_or_404(name, release_id)
        rows = _rows_or_404(name, area, start, end, resolved, explicit=release_id is not None)
        logger.info(
            "route=%s metric=%s release=%s status=200 request_id=%s",
            request.url.path,
            name,
            resolved,
            request.state.request_id,
        )
        return JSONResponse(status_code=200, content=[_observation_json(obs) for obs in rows])

    @app.get("/v1/metrics")
    async def metrics(
        request: Request,
        metric: str,
        area: str,
        from_s: From,
        to_s: To,
        release_id: ReleaseId = None,
    ) -> JSONResponse:
        return _metrics(request, metric, area, from_s, to_s, release_id)

    @app.get("/v1/prices")
    async def prices(
        request: Request, area: str, from_s: From, to_s: To, release_id: ReleaseId = None
    ) -> JSONResponse:
        return _metrics(request, _METRIC_ALIASES["prices"], area, from_s, to_s, release_id)

    @app.get("/v1/generation-mix")
    async def generation_mix(
        request: Request, area: str, from_s: From, to_s: To, release_id: ReleaseId = None
    ) -> JSONResponse:
        return _metrics(request, _METRIC_ALIASES["generation-mix"], area, from_s, to_s, release_id)

    @app.get("/v1/summary")
    async def summary(
        request: Request,
        metric: str,
        area: str,
        from_s: From,
        to_s: To,
        release_id: ReleaseId = None,
    ) -> JSONResponse:
        _, name, start, end = validate_request(area, metric, from_s, to_s, active_guard)
        resolved = _resolve_or_404(name, release_id)
        result = query.summarize(name, area, start, end, resolved)
        logger.info(
            "route=/v1/summary metric=%s release=%s status=200 request_id=%s",
            name,
            resolved,
            request.state.request_id,
        )
        return JSONResponse(
            status_code=200,
            content={
                "count": result.count,
                "min": result.minimum,
                "max": result.maximum,
                "unit": result.unit,
            },
        )

    return app
