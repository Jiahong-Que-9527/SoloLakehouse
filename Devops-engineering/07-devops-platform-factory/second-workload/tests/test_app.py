import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import freshness.app as app_module
from expected import EXPECTED_FRESH, EXPECTED_STALE, NOW

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture()
def client_with(monkeypatch):
    def build(target: Path | None) -> TestClient:
        monkeypatch.setenv("FRESHNESS_NOW", NOW)
        monkeypatch.setenv("MAX_AGE_HOURS", "24")
        if target is None:
            monkeypatch.delenv("FRESHNESS_SNAPSHOT_PATH", raising=False)
        else:
            monkeypatch.setenv("FRESHNESS_SNAPSHOT_PATH", str(target))
        return TestClient(app_module.app)

    return build


def test_fresh_fixture_verdict(client_with):
    response = client_with(FIXTURES / "snapshot-fresh.json").get("/v1/freshness/latest")
    assert response.status_code == 200
    assert response.json() == EXPECTED_FRESH


def test_stale_fixture_is_a_valid_200_answer(client_with):
    response = client_with(FIXTURES / "snapshot-stale.json").get("/v1/freshness/latest")
    assert response.status_code == 200
    assert response.json() == EXPECTED_STALE


def test_live_is_always_200(client_with):
    assert client_with(None).get("/live").status_code == 200


def test_ready_503_for_missing_snapshot(client_with, tmp_path):
    response = client_with(tmp_path / "absent.json").get("/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "snapshot_unavailable"
    assert str(tmp_path) not in response.text


def test_malformed_fixture_is_invalid(client_with):
    response = client_with(FIXTURES / "snapshot-malformed.json").get("/v1/freshness/latest")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "snapshot_invalid"


def test_unsupported_schema_version(client_with, tmp_path):
    document = {"schema_version": 2, "snapshot_id": "x", "snapshot_generated_at": NOW}
    target = tmp_path / "future.json"
    target.write_text(json.dumps(document))
    response = client_with(target).get("/v1/freshness/latest")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "snapshot_invalid"


def test_naive_timestamp_rejected(client_with, tmp_path):
    document = {
        "schema_version": 1,
        "snapshot_id": "x",
        "snapshot_generated_at": "2026-06-09T23:00:00",
    }
    target = tmp_path / "naive.json"
    target.write_text(json.dumps(document))
    response = client_with(target).get("/v1/freshness/latest")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "snapshot_invalid"


def test_boundary_age_is_fresh(client_with, tmp_path):
    document = {
        "schema_version": 1,
        "snapshot_id": "boundary",
        "snapshot_generated_at": "2026-06-09T00:00:00Z",
    }
    target = tmp_path / "boundary.json"
    target.write_text(json.dumps(document))
    body = client_with(target).get("/v1/freshness/latest").json()
    assert body["verdict"] == "fresh"
    assert body["age_hours"] == 24.0


def test_metrics_expose_signals(client_with):
    client = client_with(FIXTURES / "snapshot-fresh.json")
    client.get("/v1/freshness/latest")
    body = client.get("/metrics").text
    assert 'http_requests_total{code="200",route="/v1/freshness/latest"}' in body
    assert 'snapshot_freshness{snapshot_id="meter-snapshot-20260608"} 1.0' in body


def test_stale_gauge_is_zero(client_with):
    client = client_with(FIXTURES / "snapshot-stale.json")
    client.get("/v1/freshness/latest")
    body = client.get("/metrics").text
    assert 'snapshot_freshness{snapshot_id="meter-snapshot-20260601"} 0.0' in body
