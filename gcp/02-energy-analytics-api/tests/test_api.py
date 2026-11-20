"""Task 1.4: the frozen HTTP contract over an injected QueryPort."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from energy_api.app import create_app
from energy_api.query import FakeQueryLayer
from energy_api.seed import RELEASE_SEED

WINDOW = "2026-06-08T00:00:00Z"


def _client() -> TestClient:
    return TestClient(create_app(FakeQueryLayer(releases=RELEASE_SEED)))


def _query(path: str, **params: str) -> str:
    base = f"{path}?area=DE&from={WINDOW}&to=2026-06-08T00%3A30%3A00Z"
    return base + (f"&{params}" if params else "")


def test_health_never_touches_the_query_layer():
    class ExplodingLayer(FakeQueryLayer):
        def resolve_release(self, metric: str):
            message = "no data access from health"
            raise AssertionError(message)

    response = TestClient(create_app(ExplodingLayer(releases=RELEASE_SEED))).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_metrics_happy_path_returns_latest_release_row():
    response = _client().get(
        f"/v1/metrics?metric=actual_load_mwh&area=DE&from={WINDOW}&to=2026-06-08T00%3A30%3A00Z"
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0] == {
        "interval_start": "2026-06-08T00:15:00Z",
        "interval_end": "2026-06-08T00:30:00Z",
        "area": "DE",
        "metric": "actual_load_mwh",
        "value": 12.0,
        "unit": "MWh",
        "release_id": "seed-2026-06-08-b",
    }


def test_metrics_with_explicit_release_returns_that_release():
    response = _client().get(
        "/v1/metrics?metric=actual_load_mwh&area=DE&from=2026-06-08T00%3A00%3A00Z"
        "&to=2026-06-08T00%3A30%3A00Z&release_id=seed-2026-06-08-a"
    )
    assert response.status_code == 200
    assert [row["value"] for row in response.json()] == [10.0]


def test_empty_window_is_200_with_empty_list():
    response = _client().get(
        "/v1/metrics?metric=actual_load_mwh&area=DE&from=2026-06-08T01%3A00%3A00Z"
        "&to=2026-06-08T01%3A15%3A00Z"
    )
    assert response.status_code == 200
    assert response.json() == []


def test_reversed_range_is_400_invalid_range():
    response = _client().get(
        "/v1/metrics?metric=actual_load_mwh&area=DE&from=2026-06-09T00%3A00%3A00Z"
        "&to=2026-06-08T00%3A00%3A00Z"
    )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_range"


def test_span_guards_win_over_unknown_metric():
    # Review Focus #3: one request with both faults must answer 400
    # query_rejected (span), never 404 metric_not_published.
    response = _client().get(
        "/v1/metrics?metric=generation_mix&area=DE&from=2026-06-08T00%3A00%3A00Z"
        "&to=2026-07-10T00%3A00%3A00Z"
    )
    assert response.status_code == 400
    assert response.json()["code"] == "query_rejected"


def test_unknown_metric_is_404_metric_not_published():
    response = _client().get(
        f"/v1/metrics?metric=generation_mix&area=DE&from={WINDOW}&to=2026-06-08T00%3A30%3A00Z"
    )
    assert response.status_code == 404
    assert response.json()["code"] == "metric_not_published"


def test_unknown_explicit_release_is_404():
    response = _client().get(
        "/v1/metrics?metric=actual_load_mwh&area=DE&from=2026-06-08T00%3A00%3A00Z"
        "&to=2026-06-08T00%3A30%3A00Z&release_id=does-not-exist"
    )
    assert response.status_code == 404
    assert response.json()["code"] == "metric_not_published"


def test_prices_alias_is_fixed_metric_and_404_until_published():
    response = _client().get(f"/v1/prices?area=DE&from={WINDOW}&to=2026-06-08T00%3A30%3A00Z")
    assert response.status_code == 404
    assert response.json()["code"] == "metric_not_published"


def test_generation_mix_alias_404_until_published():
    response = _client().get(
        f"/v1/generation-mix?area=DE&from={WINDOW}&to=2026-06-08T00%3A30%3A00Z"
    )
    assert response.status_code == 404
    assert response.json()["code"] == "metric_not_published"


def test_summary_happy_path():
    response = _client().get(
        f"/v1/summary?metric=actual_load_mwh&area=DE&from={WINDOW}&to=2026-06-08T00%3A30%3A00Z"
    )
    assert response.status_code == 200
    assert response.json() == {"count": 1, "min": 12.0, "max": 12.0, "unit": "MWh"}


def test_error_shape_has_exactly_code_message_request_id():
    response = _client().get(
        "/v1/metrics?metric=actual_load_mwh&area=FR&from=2026-06-08T00%3A00%3A00Z"
        "&to=2026-06-08T00%3A30%3A00Z"
    )
    assert set(response.json()) == {"code", "message", "request_id"}


def test_request_id_header_and_body_agree_on_errors():
    response = _client().get(
        "/v1/metrics?metric=actual_load_mwh&area=FR&from=2026-06-08T00%3A00%3A00Z"
        "&to=2026-06-08T00%3A30%3A00Z"
    )
    body = response.json()
    assert response.headers["X-Request-Id"] == body["request_id"]
    assert body["request_id"]


def test_openapi_document_is_served():
    response = _client().get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert {"/health", "/v1/metrics", "/v1/summary", "/v1/prices", "/v1/generation-mix"} <= set(
        paths
    )


def test_app_factory_builds_an_independent_app():
    first = create_app(FakeQueryLayer(releases=RELEASE_SEED))
    second = create_app(FakeQueryLayer(releases=RELEASE_SEED))
    assert first is not second


def test_iso_strings_are_utc_rfc3339():
    response = _client().get(
        f"/v1/metrics?metric=actual_load_mwh&area=DE&from={WINDOW}&to=2026-06-08T00%3A30%3A00Z"
    )
    row = response.json()[0]
    parsed = datetime.fromisoformat(row["interval_start"].replace("Z", "+00:00"))
    assert parsed.utcoffset() == UTC.utcoffset(parsed)
