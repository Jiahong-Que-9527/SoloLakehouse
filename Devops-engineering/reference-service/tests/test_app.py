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
