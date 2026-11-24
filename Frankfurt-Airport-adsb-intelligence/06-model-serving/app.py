"""Local HTTP scoring for one pinned EDDF taxi-in model release."""

import hashlib
import json
import logging
import math
import os
import pickle
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

import numpy as np
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from pydantic import AwareDatetime, BaseModel, ConfigDict, StrictFloat, field_validator

LOGGER = logging.getLogger("uvicorn.error")
FEATURES = (
    "approach_speed_mps", "approach_altitude_m", "approach_vertical_rate_mps",
    "approach_distance_m", "ground_speed_mps", "approach_age_s", "prediction_hour_utc",
)


class ArrivalFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    approach_speed_mps: StrictFloat | None
    approach_altitude_m: StrictFloat | None
    approach_vertical_rate_mps: StrictFloat | None
    approach_distance_m: StrictFloat
    ground_speed_mps: StrictFloat | None
    approach_age_s: StrictFloat


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    airport_icao: Literal["EDDF"]
    prediction_at: AwareDatetime
    features: ArrivalFeatures

    @field_validator("prediction_at", mode="before")
    @classmethod
    def require_timestamp_string(cls, value):
        if not isinstance(value, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)", value
        ):
            raise ValueError("prediction_at must be an RFC 3339 timestamp with offset")
        try:
            return datetime.fromisoformat(value).astimezone(UTC)
        except (OverflowError, ValueError) as exc:
            raise ValueError("prediction_at must be a valid UTC-convertible timestamp") from exc


class ModelLineage(BaseModel):
    model_release_id: str
    model_version: int
    source_commit: str
    manifest_sha256: str
    artifact_sha256: str


class PredictionResponse(BaseModel):
    airport_icao: Literal["EDDF"]
    prediction_at: AwareDatetime
    predicted_taxi_in_seconds: float
    model: ModelLineage


@dataclass(frozen=True)
class PinnedModel:
    estimator: object
    lineage: ModelLineage

    def predict(self, request: PredictionRequest) -> float:
        values = request.features.model_dump()
        values["prediction_hour_utc"] = request.prediction_at.hour
        matrix = np.asarray([[values[name] for name in FEATURES]], dtype=np.float64)
        seconds = float(self.estimator.predict(matrix)[0])
        if not math.isfinite(seconds):
            raise ValueError("model produced a non-finite prediction")
        return seconds


def load_model(release_dir: Path, expected_digest: str) -> PinnedModel:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
        raise ValueError("MODEL_MANIFEST_SHA256 must contain the pinned manifest SHA-256")
    raw = (release_dir / "manifest.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_digest:
        raise ValueError("model release manifest does not match the pinned SHA-256")
    manifest = json.loads(raw)
    registry = manifest["registry"]
    version = registry["version"]
    if (manifest["schema_version"] != "frankfurt-airport-model-release-v1"
            or manifest["feature_columns"] != list(FEATURES)
            or manifest["artifact"]["path"] != "model.pkl"
            or not re.fullmatch(r"frankfurt-airport-taxi-in-[0-9a-f]{16}", manifest["model_release_id"])
            or not re.fullmatch(r"[0-9a-f]{40}", manifest["source_commit"])
            or type(version) is not int or version < 1
            or registry["model_name"] != "frankfurt-airport-taxi-in"
            or registry["model_uri"] != f"models:/frankfurt-airport-taxi-in/{version}"):
        raise ValueError("model manifest does not match the EDDF serving contract")
    artifact = (release_dir / "model.pkl").read_bytes()
    digest = hashlib.sha256(artifact).hexdigest()
    if digest != manifest["artifact"]["sha256"]:
        raise ValueError("model artifact does not match the release SHA-256")
    # The operator supplies the trusted release pin. Deserialize only the verified bytes.
    bundle = pickle.loads(artifact)
    if bundle["feature_columns"] != list(FEATURES) or not callable(getattr(bundle["estimator"], "predict", None)):
        raise ValueError("model artifact does not match the EDDF serving contract")
    lineage = ModelLineage(model_release_id=manifest["model_release_id"], model_version=version,
                           source_commit=manifest["source_commit"], manifest_sha256=expected_digest,
                           artifact_sha256=digest)
    return PinnedModel(bundle["estimator"], lineage)


def create_app(model: PinnedModel) -> FastAPI:
    app = FastAPI(title="EDDF Taxi-in Prediction")
    registry = CollectorRegistry()
    requests = Counter("eddf_prediction_requests", "Prediction requests by HTTP status class.",
                       ["status_class"], registry=registry)
    duration = Histogram("eddf_prediction_request_duration_seconds", "Prediction handler duration in seconds.",
                         registry=registry)
    Gauge("eddf_serving_model_info", "The model pinned by this process.",
          ["model_release_id", "model_version"], registry=registry).labels(
              model.lineage.model_release_id, str(model.lineage.model_version)).set(1)
    for status_class in ("2xx", "4xx", "5xx"):
        requests.labels(status_class)

    @app.middleware("http")
    async def record_request(request: Request, call_next):
        request.state.request_id = uuid4().hex
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
        finally:
            elapsed = time.perf_counter() - start
            if request.method == "POST" and request.url.path == "/v1/predict":
                requests.labels(f"{status // 100}xx").inc()
                duration.observe(elapsed)
        response.headers["X-Request-Id"] = request.state.request_id
        LOGGER.info("%s", json.dumps({
            "request_id": request.state.request_id, "route": getattr(request.scope.get("route"), "path", None),
            "status": status, "latency_ms": round(elapsed * 1000, 2),
            "model_release_id": model.lineage.model_release_id,
        }))
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, _exc: RequestValidationError):
        return JSONResponse(status_code=400, content={
            "code": "invalid_parameters", "message": "request body does not match the EDDF prediction contract",
            "request_id": request.state.request_id,
        })

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    @app.get("/v1/model", response_model=ModelLineage)
    async def model_lineage():
        return model.lineage

    @app.post("/v1/predict", response_model=PredictionResponse)
    async def predict(body: PredictionRequest, request: Request):
        try:
            seconds = model.predict(body)
        except (IndexError, TypeError, ValueError):
            LOGGER.exception("Prediction failed for request_id=%s", request.state.request_id)
            return JSONResponse(status_code=500, content={
                "code": "prediction_failed", "message": "the pinned model could not calculate a prediction",
                "request_id": request.state.request_id,
            })
        return PredictionResponse(airport_icao=body.airport_icao, prediction_at=body.prediction_at,
                                  predicted_taxi_in_seconds=seconds, model=model.lineage)

    return app


def from_environment() -> FastAPI:
    return create_app(load_model(Path(os.environ["MODEL_RELEASE_DIR"]), os.environ["MODEL_MANIFEST_SHA256"]))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(from_environment(), host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), access_log=False)
