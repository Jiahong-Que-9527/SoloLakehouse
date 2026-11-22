"""M06 · HTTP serving of the pinned release (the G02 application shape).

`create_app()` builds the frozen contract around an injected scoring port —
tests inject a fake, the CLI wires the real pinned release. Error mapping:
`invalid_parameters` / `invalid_range` are HTTP 400, `issue_not_scoreable`
is HTTP 422, and every error body is exactly {"code", "message",
"request_id"}. Every response carries X-Request-Id and every prediction
response carries the model lineage, so any served number traces to the
release manifest and commit. The service refuses to start without a pin —
nothing downstream reads an unpinned model.
"""

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, date
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from charging_forecast.contract import issue_time_utc
from charging_forecast.eval import load_demand
from charging_forecast.serving import (
    Release,
    _feature_release_guard,
    _iso_us,
    _predict_day,
)

logger = logging.getLogger("charging_serving")


@dataclass(frozen=True)
class ServingGuard:
    """Request bounds (the G02 guard discipline: parameters, then range,
    then scoreability)."""

    max_stations_per_request: int = 40
    timeout_seconds: int = 15


class ValidationError(Exception):
    """A request that never reaches the model; carries the error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ScoringPort:
    """What the API needs from a release surface; tests substitute fakes."""

    def lineage(self) -> dict:  # pragma: no cover - interface only
        raise NotImplementedError

    def stations(self) -> list[str]:  # pragma: no cover - interface only
        raise NotImplementedError

    def issue_bounds(self) -> tuple[str, str]:  # pragma: no cover - interface only
        raise NotImplementedError

    def predict_rows(self, issue_date: str, stations: list[str] | None) -> list[dict]:
        raise NotImplementedError


class PinnedScoringPort(ScoringPort):
    """The real port: scores issue days with the pinned artifact through the
    contract read path, carrying the pinned manifest's lineage."""

    def __init__(
        self,
        pinned: Release,
        release_dir: Path,
        cfg: dict,
        features_dir: Path,
    ) -> None:
        self.pinned = pinned
        self.release_dir = Path(release_dir)
        self.cfg = cfg
        self.features_dir = Path(features_dir)
        self._feature_release_id = _feature_release_guard(pinned, self.features_dir)
        self._demand = load_demand(self.release_dir, cfg)
        fmanifest = json.loads((self.features_dir / "manifest.json").read_text(encoding="utf-8"))
        self._bounds = (fmanifest["issue_start"], fmanifest["issue_end"])

    def lineage(self) -> dict:
        m = self.pinned.manifest
        return {
            "model_release_id": self.pinned.model_release_id,
            "mlflow_model_version": m["mlflow_model_version"],
            "git_sha": m["source_commit"],
            "data_release_id": m["data_release_id"],
            "feature_release_id": self._feature_release_id,
            "metrics": m["metrics"],
            "manifest_sha256": self.pinned.manifest_sha256,
        }

    def stations(self) -> list[str]:
        return list(self._demand.stations)

    def issue_bounds(self) -> tuple[str, str]:
        return self._bounds

    def predict_rows(self, issue_date: str, stations: list[str] | None) -> list[dict]:
        day = date.fromisoformat(issue_date)
        station_ids, target_us, preds, _ = _predict_day(
            self.pinned, self.release_dir, self.cfg, self.features_dir, day
        )
        rows = [
            {
                "station_id": sid,
                "target_time": _iso_us(int(us)),
                "predicted_kwh": round(float(p), 6),
            }
            for sid, us, p in zip(
                station_ids.tolist(), target_us.tolist(), preds.tolist(), strict=True
            )
        ]
        if stations is not None:
            wanted = set(stations)
            rows = [row for row in rows if row["station_id"] in wanted]
        return rows


class PredictRequest(BaseModel):
    issue_date: str
    stations: list[str] | None = None


def _parse_issue_date(value: str) -> date:
    if len(value) != 10:
        raise ValidationError(
            code="invalid_parameters", message="issue_date must be an ISO calendar date YYYY-MM-DD"
        )
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(
            code="invalid_parameters", message="issue_date must be an ISO calendar date YYYY-MM-DD"
        ) from exc


def create_app(port: ScoringPort, guard: ServingGuard | None = None) -> FastAPI:
    """Build one app instance around one pinned release surface; tests inject
    the port."""
    app = FastAPI(title="Charging Forecast API")
    active_guard = guard or ServingGuard()

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        return response

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        status = 422 if exc.code == "issue_not_scoreable" else 400
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

    @app.exception_handler(RequestValidationError)
    async def body_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=400,
            content={
                "code": "invalid_parameters",
                "message": "request body does not match the contract",
                "request_id": request.state.request_id,
            },
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/model")
    async def model(request: Request) -> JSONResponse:
        logger.info(
            "route=/v1/model model=%s status=200 request_id=%s",
            port.lineage()["model_release_id"],
            request.state.request_id,
        )
        return JSONResponse(status_code=200, content=port.lineage())

    @app.post("/v1/predict")
    async def predict(request: Request, body: PredictRequest) -> JSONResponse:
        day = _parse_issue_date(body.issue_date)
        lo, hi = port.issue_bounds()
        if not (date.fromisoformat(lo) <= day <= date.fromisoformat(hi)):
            raise ValidationError(
                code="invalid_range",
                message=f"issue_date {body.issue_date} is outside the scoreable range {lo}..{hi}",
            )
        if body.stations is not None:
            unknown = sorted(set(body.stations) - set(port.stations()))
            if unknown:
                raise ValidationError(
                    code="invalid_parameters",
                    message=f"unknown stations: {', '.join(unknown)}",
                )
            if len(body.stations) > active_guard.max_stations_per_request:
                raise ValidationError(
                    code="invalid_parameters",
                    message=(
                        f"stations list exceeds the budget of "
                        f"{active_guard.max_stations_per_request} per request"
                    ),
                )
        rows = port.predict_rows(body.issue_date, body.stations)
        if not rows:
            raise ValidationError(
                code="issue_not_scoreable",
                message=f"no feature rows are materialized for issue date {body.issue_date}",
            )
        lineage = port.lineage()
        payload = {
            "model_release_id": lineage["model_release_id"],
            "mlflow_model_version": lineage["mlflow_model_version"],
            "git_sha": lineage["git_sha"],
            "issue_date": body.issue_date,
            "issue_time_utc": issue_time_utc(day).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "predictions": rows,
        }
        logger.info(
            "route=/v1/predict issue=%s rows=%d status=200 request_id=%s",
            body.issue_date,
            len(rows),
            request.state.request_id,
        )
        return JSONResponse(status_code=200, content=payload)

    return app
