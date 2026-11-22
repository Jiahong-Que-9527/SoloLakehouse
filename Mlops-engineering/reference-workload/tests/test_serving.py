"""M06 serving tests: batch scoring idempotence and lineage, the score
collision guard, the shadow report, the HTTP contract and a bounded load
check — mirroring the G02 test shapes."""

from __future__ import annotations

import json
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from charging_forecast import pipeline as pipeline_mod
from charging_forecast import serving as serving_mod
from charging_forecast.api import (
    PinnedScoringPort,
    ScoringPort,
    ServingGuard,
    create_app,
)
from charging_forecast.contract import load_config, sha256_file
from charging_forecast.eval import valid_issue_range
from charging_forecast.features import FeatureBuilder
from charging_forecast.generator import ChargingGenerator
from conftest import publish_manifest, write_config

# The M03/M04 test window: long enough for real folds, small enough to train
# twice in seconds.
EVAL_WINDOW = {"start": "2025-01-01T00:00:00Z", "end": "2025-04-20T23:00:00Z"}
SMALL_GRID = {"learning_rate": [0.1], "max_leaf_nodes": [15], "min_samples_leaf": [10]}
SELECTION = dict(
    sel_train_end=date(2025, 3, 5),
    sel_val_start=date(2025, 3, 6),
    sel_val_end=date(2025, 3, 31),
)


@pytest.fixture(scope="module")
def m06_env(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("m06")
    config_path = write_config(tmp / "config.yaml", overrides={"window": EVAL_WINDOW})
    cfg = load_config(config_path)
    release = tmp / "release"
    ChargingGenerator(cfg).generate(release)
    publish_manifest(release, cfg)
    v_start, v_end = valid_issue_range(cfg)
    features = tmp / "features"
    FeatureBuilder(release, cfg).materialize(v_start, v_end, features)

    releases_dir = tmp / "releases"
    models_dir = tmp / "models"

    def train_publish(model_release_id: str, max_iter: int) -> None:
        report, artifact_path, _ = pipeline_mod.step_train(
            release,
            cfg,
            features,
            tmp / f"report-{model_release_id}",
            model_release_id,
            models_dir,
            tracking_uri=f"sqlite:///{tmp / f'ml-{model_release_id}.db'}",
            max_iter=max_iter,
            grid=SMALL_GRID,
            **SELECTION,
        )
        pipeline_mod.step_publish(
            release,
            features,
            report,
            artifact_path,
            model_release_id,
            {"version": 1, "run_id": f"test-{model_release_id}"},
            releases_dir=releases_dir,
        )

    train_publish("model-v001", 25)
    train_publish("model-v002", 40)
    _pin(releases_dir, "model-v001")
    return {
        "tmp": tmp,
        "release": release,
        "cfg": cfg,
        "features": features,
        "v_start": v_start,
        "v_end": v_end,
        "releases_dir": releases_dir,
        "models_dir": models_dir,
        "scores_dir": tmp / "scores",
        "score_releases_dir": tmp / "score-releases",
    }


def _pin(releases_dir: Path, model_release_id: str) -> None:
    manifest_path = releases_dir / model_release_id / "manifest.json"
    pin = {
        "model_release_id": model_release_id,
        "manifest_sha256": sha256_file(manifest_path),
    }
    (releases_dir / "pinned.json").write_text(
        json.dumps(pin, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


# -- the pinned release -----------------------------------------------------------


def test_pinned_release_loads_and_refuses_a_tampered_artifact(m06_env):
    pinned = serving_mod.load_pinned_release(
        releases_dir=m06_env["releases_dir"], models_dir=m06_env["models_dir"]
    )
    assert pinned.model_release_id == "model-v001"
    assert pinned.manifest["mlflow_model_version"] == 1

    artifact = m06_env["models_dir"] / "model-v001" / "model.joblib"
    original = artifact.read_bytes()
    artifact.write_bytes(original + b"tampered")
    try:
        with pytest.raises(RuntimeError, match="does not match its manifest checksum"):
            serving_mod.load_pinned_release(
                releases_dir=m06_env["releases_dir"], models_dir=m06_env["models_dir"]
            )
    finally:
        artifact.write_bytes(original)


def test_serving_refuses_to_start_without_a_pin(m06_env, tmp_path):
    empty = tmp_path / "no-pin"
    empty.mkdir()
    with pytest.raises(RuntimeError, match="no pinned release"):
        serving_mod.load_pinned_release(releases_dir=empty, models_dir=m06_env["models_dir"])


# -- batch scoring ------------------------------------------------------------------


def test_batch_scoring_is_idempotent_with_stable_checksums(m06_env):
    issue_date = m06_env["v_end"].isoformat()
    first = serving_mod.score_issue_day(
        serving_mod.load_pinned_release(
            releases_dir=m06_env["releases_dir"], models_dir=m06_env["models_dir"]
        ),
        m06_env["release"],
        m06_env["cfg"],
        m06_env["features"],
        issue_date,
        scores_dir=m06_env["scores_dir"],
        score_releases_dir=m06_env["score_releases_dir"],
    )
    assert first["reused"] is False
    manifest = first["manifest"]
    n_stations = manifest["stations"]
    assert manifest["rows"] == n_stations * 24
    assert manifest["target_window"]["start"] == "2025-04-20T00:00:00Z"
    assert manifest["target_window"]["end"] == "2025-04-20T23:00:00Z"

    parquet = m06_env["scores_dir"] / "model-v001" / issue_date / "predictions.parquet"
    committed = m06_env["score_releases_dir"] / "model-v001" / issue_date / "manifest.json"
    assert committed.exists()
    sha_before = sha256_file(parquet)

    second = serving_mod.score_issue_day(
        serving_mod.load_pinned_release(
            releases_dir=m06_env["releases_dir"], models_dir=m06_env["models_dir"]
        ),
        m06_env["release"],
        m06_env["cfg"],
        m06_env["features"],
        issue_date,
        scores_dir=m06_env["scores_dir"],
        score_releases_dir=m06_env["score_releases_dir"],
    )
    assert second["reused"] is True
    assert second["manifest"] == manifest
    assert sha256_file(parquet) == sha_before


def test_scored_rows_carry_the_pinned_lineage(m06_env):
    import pyarrow.parquet as pq

    issue_date = m06_env["v_end"].isoformat()
    table = pq.read_table(m06_env["scores_dir"] / "model-v001" / issue_date / "predictions.parquet")
    manifest = json.loads(
        (m06_env["releases_dir"] / "model-v001" / "manifest.json").read_text(encoding="utf-8")
    )
    assert table.column("model_release_id").to_pylist().count("model-v001") == table.num_rows
    assert set(table.column("mlflow_model_version").to_pylist()) == {
        manifest["mlflow_model_version"]
    }
    assert set(table.column("git_sha").to_pylist()) == {manifest["source_commit"]}
    assert table.column("target_time").null_count == 0
    predictions = table.column("predicted_kwh").to_numpy()
    assert np.isfinite(predictions).all()


def test_score_collision_refused_and_pin_content_stable(m06_env):
    issue_date = m06_env["v_end"].isoformat()
    manifest_path = m06_env["score_releases_dir"] / "model-v001" / issue_date / "manifest.json"
    original = manifest_path.read_text(encoding="utf-8")
    tampered = json.loads(original)
    tampered["rows"] = 1
    manifest_path.write_text(
        json.dumps(tampered, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    try:
        with pytest.raises(RuntimeError, match="score collision"):
            serving_mod.score_issue_day(
                serving_mod.load_pinned_release(
                    releases_dir=m06_env["releases_dir"], models_dir=m06_env["models_dir"]
                ),
                m06_env["release"],
                m06_env["cfg"],
                m06_env["features"],
                issue_date,
                scores_dir=m06_env["scores_dir"],
                score_releases_dir=m06_env["score_releases_dir"],
            )
    finally:
        manifest_path.write_text(original, encoding="utf-8")
    again = serving_mod.score_issue_day(
        serving_mod.load_pinned_release(
            releases_dir=m06_env["releases_dir"], models_dir=m06_env["models_dir"]
        ),
        m06_env["release"],
        m06_env["cfg"],
        m06_env["features"],
        issue_date,
        scores_dir=m06_env["scores_dir"],
        score_releases_dir=m06_env["score_releases_dir"],
    )
    assert again["reused"] is True


def test_scoring_refuses_a_foreign_feature_release(m06_env, tmp_path):
    forged = tmp_path / "features-forged"
    forged.mkdir()
    for entry in m06_env["features"].iterdir():
        if entry.name == "manifest.json":
            continue
        (forged / entry.name).symlink_to(entry)
    manifest = json.loads((m06_env["features"] / "manifest.json").read_text(encoding="utf-8"))
    manifest["feature_release_id"] = "feat-v9-dataset-test"
    (forged / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(RuntimeError, match="does not match the pinned feature contract"):
        serving_mod.score_issue_day(
            serving_mod.load_pinned_release(
                releases_dir=m06_env["releases_dir"], models_dir=m06_env["models_dir"]
            ),
            m06_env["release"],
            m06_env["cfg"],
            forged,
            m06_env["v_end"].isoformat(),
            scores_dir=tmp_path / "scores-forged",
        )


# -- shadow comparison ---------------------------------------------------------------


def test_shadow_report_compares_candidate_and_pinned(m06_env, tmp_path):
    pinned = serving_mod.load_pinned_release(
        releases_dir=m06_env["releases_dir"], models_dir=m06_env["models_dir"]
    )
    candidate = serving_mod.load_release(
        "model-v002", releases_dir=m06_env["releases_dir"], models_dir=m06_env["models_dir"]
    )
    out_path = tmp_path / "shadow-report.json"
    report = serving_mod.shadow_compare(
        pinned,
        candidate,
        m06_env["release"],
        m06_env["cfg"],
        m06_env["features"],
        [m06_env["v_end"].isoformat()],
        out_path=out_path,
    )
    assert report["pinned"]["model_release_id"] == "model-v001"
    assert report["candidate"]["model_release_id"] == "model-v002"
    assert report["request_set"]["stations"] > 0
    day = report["per_issue_day"][0]
    assert day["rows"] > 0
    assert 0 <= day["mean_abs_delta"] <= day["max_abs_delta"]
    assert day["pinned_mae"] is not None and day["candidate_mae"] is not None
    saved = json.loads(out_path.read_text(encoding="utf-8"))
    assert saved == report


# -- the HTTP contract (fake port, G02 test shapes) ----------------------------------


class FakePort(ScoringPort):
    """A deterministic two-station surface for the contract tests; 2025-03-15
    has no materialized rows (the issue_not_scoreable case)."""

    def __init__(
        self,
        stations: tuple[str, ...] = ("S001", "S002"),
        bounds: tuple[str, str] = ("2025-03-01", "2025-03-20"),
    ) -> None:
        self._stations = stations
        self._bounds = bounds
        self._empty_dates = {"2025-03-15"}
        self.lineage_value = {
            "model_release_id": "model-fake",
            "mlflow_model_version": 7,
            "git_sha": "abc123",
            "data_release_id": "dataset-test",
            "feature_release_id": "feat-v1-dataset-test",
            "metrics": {"model_mae": 1.0},
            "manifest_sha256": "cafe",
        }

    def lineage(self) -> dict:
        return self.lineage_value

    def stations(self) -> list[str]:
        return list(self._stations)

    def issue_bounds(self) -> tuple[str, str]:
        return self._bounds

    def predict_rows(self, issue_date: str, stations: list[str] | None) -> list[dict]:
        day = date.fromisoformat(issue_date)
        if issue_date in self._empty_dates:
            return []
        base = datetime(day.year, day.month, day.day, tzinfo=UTC) + timedelta(days=1)
        wanted = set(stations) if stations is not None else set(self._stations)
        return [
            {
                "station_id": sid,
                "target_time": (base + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "predicted_kwh": 1.5,
            }
            for sid in sorted(wanted)
            for h in range(24)
        ]


@pytest.fixture()
def client():
    return TestClient(create_app(FakePort(), ServingGuard(max_stations_per_request=3)))


def test_health_and_model_lineage(client):
    assert client.get("/health").json() == {"status": "ok"}
    response = client.get("/v1/model")
    assert response.status_code == 200
    body = response.json()
    assert body["model_release_id"] == "model-fake"
    assert body["mlflow_model_version"] == 7
    assert body["git_sha"] == "abc123"


def test_predict_returns_rows_with_lineage_and_request_id(client):
    response = client.post("/v1/predict", json={"issue_date": "2025-03-10"})
    assert response.status_code == 200
    body = response.json()
    assert body["model_release_id"] == "model-fake"
    assert body["mlflow_model_version"] == 7
    assert body["git_sha"] == "abc123"
    assert body["issue_date"] == "2025-03-10"
    assert len(body["predictions"]) == 48
    assert body["predictions"][0]["station_id"] == "S001"
    assert response.headers["X-Request-Id"]


def test_same_request_same_version_same_prediction(client):
    first = client.post("/v1/predict", json={"issue_date": "2025-03-10"}).json()
    second = client.post("/v1/predict", json={"issue_date": "2025-03-10"}).json()
    first.pop("predictions")
    second.pop("predictions")
    assert first == second


def test_predict_filters_requested_stations(client):
    response = client.post("/v1/predict", json={"issue_date": "2025-03-10", "stations": ["S002"]})
    body = response.json()
    assert {row["station_id"] for row in body["predictions"]} == {"S002"}


def test_error_bodies_are_exactly_code_message_request_id(client):
    for payload, code, status in [
        ({"issue_date": "10-03-2025"}, "invalid_parameters", 400),
        ({"issue_date": "2025-03-10", "stations": ["S999"]}, "invalid_parameters", 400),
        ({"issue_date": "2025-06-01"}, "invalid_range", 400),
        ({"issue_date": "2024-06-01"}, "invalid_range", 400),
        (
            {"issue_date": "2025-03-10", "stations": ["S001", "S002", "S003", "S004"]},
            "invalid_parameters",
            400,
        ),
        ({"issue_date": "2025-03-15"}, "issue_not_scoreable", 422),
    ]:
        response = client.post("/v1/predict", json=payload)
        assert response.status_code == status, payload
        assert set(response.json()) == {"code", "message", "request_id"}, payload
        assert response.json()["code"] == code, payload


def test_malformed_body_maps_to_invalid_parameters(client):
    response = client.post(
        "/v1/predict", content=b"{not json", headers={"content-type": "application/json"}
    )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_parameters"


def test_port_without_a_pin_refuses_construction(m06_env, tmp_path):
    empty = tmp_path / "no-pin"
    empty.mkdir()
    with pytest.raises(RuntimeError, match="no pinned release"):
        PinnedScoringPort(
            serving_mod.load_pinned_release(releases_dir=empty, models_dir=m06_env["models_dir"]),
            m06_env["release"],
            m06_env["cfg"],
            m06_env["features"],
        )


# -- bounded load check (the real port) -----------------------------------------------


def test_bounded_load_check_records_p95_and_error_behavior(m06_env):
    port = PinnedScoringPort(
        serving_mod.load_pinned_release(
            releases_dir=m06_env["releases_dir"], models_dir=m06_env["models_dir"]
        ),
        m06_env["release"],
        m06_env["cfg"],
        m06_env["features"],
    )
    client = TestClient(create_app(port))
    issue_date = m06_env["v_end"].isoformat()
    invalid_specs = [
        {"json": {"issue_date": "2026-06-01"}, "want": 400},  # invalid_range
        {"json": {"issue_date": "not-a-date"}, "want": 400},  # invalid_parameters
        {"json": {"issue_date": issue_date, "stations": ["S999"]}, "want": 400},
    ]
    requests = [{"json": {"issue_date": issue_date}, "want": 200} for _ in range(40)] + [
        dict(spec) for spec in invalid_specs for _ in range(4)
    ]
    latencies_ms, codes = [], {}
    for spec in requests:
        want = spec.pop("want")
        start = time.perf_counter()
        response = client.post("/v1/predict", **spec)
        latencies_ms.append((time.perf_counter() - start) * 1000)
        codes[f"{response.status_code}"] = codes.get(f"{response.status_code}", 0) + 1
        assert response.status_code == want
    p95 = float(np.percentile(latencies_ms, 95))
    print(
        f"load check: n={len(requests)}, p95={p95:.1f} ms, max={max(latencies_ms):.1f} ms, "
        f"status counts={codes}"
    )
    assert p95 < 2000, f"p95 latency {p95:.1f} ms breaches the bounded budget"
    assert codes["200"] == 40 and codes["400"] == 12
