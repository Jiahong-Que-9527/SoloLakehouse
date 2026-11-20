import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import energy_quality.app as app_module
from expected import EXPECTED_FAILED, EXPECTED_PASSED

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture()
def client_with(monkeypatch):
    def build(target: Path | None) -> TestClient:
        if target is None:
            monkeypatch.delenv("AUDIT_REPORT_PATH", raising=False)
        else:
            monkeypatch.setenv("AUDIT_REPORT_PATH", str(target))
        return TestClient(app_module.app)

    return build


def test_live_is_always_200(client_with):
    response = client_with(None).get("/live")
    assert response.status_code == 200
    assert response.json() == {"status": "live"}


def test_ready_is_200_for_a_readable_report(client_with):
    response = client_with(FIXTURES / "report-passed.json").get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_quality_serves_the_passed_fixture_verbatim(client_with):
    response = client_with(FIXTURES / "report-passed.json").get("/v1/quality/latest")
    assert response.status_code == 200
    assert response.json() == EXPECTED_PASSED


def test_failed_audit_stays_readable_with_http_200(client_with):
    response = client_with(FIXTURES / "report-failed.json").get("/v1/quality/latest")
    assert response.status_code == 200
    assert response.json() == EXPECTED_FAILED
    assert response.json()["coverage_result"] == "failed"


def test_missing_report_is_unavailable_without_paths(client_with, tmp_path):
    response = client_with(tmp_path / "absent.json").get("/v1/quality/latest")
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "report_unavailable"
    assert str(tmp_path) not in response.text


def test_ready_is_503_for_a_missing_report(client_with, tmp_path):
    response = client_with(tmp_path / "absent.json").get("/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "report_unavailable"


def test_unconfigured_report_is_unavailable(client_with):
    response = client_with(None).get("/v1/quality/latest")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "report_unavailable"


def test_malformed_fixture_is_invalid(client_with):
    response = client_with(FIXTURES / "report-malformed.json").get("/v1/quality/latest")
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "report_invalid"
    assert "missing" in body["error"]["message"].lower()


def test_unsupported_schema_version_is_invalid(client_with, tmp_path):
    document = dict(EXPECTED_PASSED, schema_version=99)
    target = tmp_path / "future.json"
    target.write_text(json.dumps(document))
    response = client_with(target).get("/v1/quality/latest")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "report_invalid"


def test_metrics_expose_requests_and_audit_gauge(client_with):
    client = client_with(FIXTURES / "report-passed.json")
    client.get("/v1/quality/latest")
    body = client.get("/metrics").text
    assert 'http_requests_total{code="200",route="/v1/quality/latest"}' in body
    assert "audit_coverage_result" in body
    assert "http_request_duration_seconds" in body


def test_metrics_record_availability_errors(client_with, tmp_path):
    client = client_with(tmp_path / "absent.json")
    client.get("/v1/quality/latest")
    body = client.get("/metrics").text
    assert 'http_requests_total{code="503",route="/v1/quality/latest"}' in body
    assert 'audit_coverage_result{report_id="unavailable"} 0.0' in body
