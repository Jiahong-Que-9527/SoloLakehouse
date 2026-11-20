"""Task 2.1: GCP adapter contract tests with a fake bigquery module.

The fake mirrors the slice of the real client the adapter uses:
query(sql, job_config=...) -> job; job.result(timeout=...) -> rows.
Guard values must land on the job config and the result timeout; BigQuery
errors must translate to ValidationError(query_rejected) — fail closed.
"""

import concurrent.futures
import sys
import types
from datetime import UTC, datetime

import pytest

from energy_api.cloud_gcp import GcpQueryLayer
from energy_api.guards import QueryGuard, ValidationError


class FakeJob:
    def __init__(self, rows, timeout=None):
        self._rows = rows
        self._timeout = timeout

    def result(self, timeout=None):
        assert timeout is not None, "result must carry the guard timeout"
        assert timeout == self._timeout
        return list(self._rows)


class FakeBigQueryClient:
    """Mirrors the slice of the real client that GcpQueryLayer uses."""

    project = "proj"

    def __init__(self, rows=None, fail_with=None):
        self.rows = rows or []
        self.fail_with = fail_with
        self.calls = []  # (sql, job_config, timeout)

    def query(self, sql, job_config=None, timeout=None):
        self.calls.append((sql, job_config, timeout))
        if self.fail_with is not None:
            raise self.fail_with
        return FakeJob(self.rows, timeout=self.guard_timeout)

    guard_timeout = 15


def _install_fake_bigquery(monkeypatch, client, bad_request=None):
    """Make google.cloud.bigquery and google.api_core.exceptions resolve to fakes."""
    google = types.ModuleType("google")
    cloud = types.ModuleType("google.cloud")
    bigquery = types.ModuleType("google.cloud.bigquery")
    bigquery.Client = lambda: client
    bigquery.QueryJobConfig = lambda **kw: types.SimpleNamespace(**kw)
    bigquery.ScalarQueryParameter = lambda name, type_, value: (name, type_, value)
    google.cloud = cloud
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud)
    monkeypatch.setitem(sys.modules, "google.cloud.bigquery", bigquery)
    if bad_request is not None:
        api_core = types.ModuleType("google.api_core")
        exceptions = types.ModuleType("google.api_core.exceptions")
        exceptions.BadRequest = bad_request
        api_core.exceptions = exceptions
        monkeypatch.setitem(sys.modules, "google.api_core", api_core)
        monkeypatch.setitem(sys.modules, "google.api_core.exceptions", exceptions)


def _layer(client, guard=None):
    return GcpQueryLayer(
        dataset="energy_api", view="metric_observation", guard=guard, client=client
    )


def _row(**overrides):
    row = {
        "interval_start": datetime(2026, 6, 8, 0, 15, tzinfo=UTC),
        "interval_end": datetime(2026, 6, 8, 0, 30, tzinfo=UTC),
        "area": "DE",
        "metric": "actual_load_mwh",
        "value": 12.0,
        "unit": "MWh",
        "release_id": "seed-2026-06-08-b",
    }
    row.update(overrides)
    return row


def test_fetch_observations_is_parameterised_and_honours_guards(monkeypatch):
    client = FakeBigQueryClient(rows=[_row()])
    _install_fake_bigquery(monkeypatch, client)
    guard = QueryGuard()
    layer = _layer(client, guard)

    rows = layer.fetch_observations(
        metric="actual_load_mwh",
        area="DE",
        start=datetime(2026, 6, 8, tzinfo=UTC),
        end=datetime(2026, 6, 8, 1, tzinfo=UTC),
        release_id="seed-2026-06-08-b",
    )

    sql, job_config, _timeout = client.calls[0]
    # SQL is a constant template: no user value may be interpolated into it.
    assert "actual_load_mwh" not in sql and "seed-2026-06-08-b" not in sql
    assert "@metric" in sql and "@start" in sql and "< @end" in sql
    assert job_config.maximum_bytes_billed == guard.max_bytes_billed
    assert ("metric", "STRING", "actual_load_mwh") in job_config.query_parameters
    assert ("start", "TIMESTAMP", datetime(2026, 6, 8, tzinfo=UTC)) in job_config.query_parameters
    assert ("end", "TIMESTAMP", datetime(2026, 6, 8, 1, tzinfo=UTC)) in job_config.query_parameters
    assert len(rows) == 1
    assert rows[0].value == 12.0
    assert rows[0].interval_start.utcoffset() is not None


def test_resolve_release_uses_the_view_not_the_ledger(monkeypatch):
    client = FakeBigQueryClient(rows=[{"release_id": "seed-2026-06-08-b"}])
    _install_fake_bigquery(monkeypatch, client)

    assert _layer(client).resolve_release("actual_load_mwh") == "seed-2026-06-08-b"
    sql, _cfg, _timeout = client.calls[0]
    assert "energy.metric_observation" not in sql  # ledger table must not appear
    assert "energy_api" in sql


def test_resolve_release_without_rows_is_none(monkeypatch):
    client = FakeBigQueryClient(rows=[])
    _install_fake_bigquery(monkeypatch, client)
    assert _layer(client).resolve_release("generation_mix") is None


def test_summarize_maps_rows_and_handles_empty(monkeypatch):
    client = FakeBigQueryClient(rows=[{"n": 1, "lo": 12.0, "hi": 12.0}])
    _install_fake_bigquery(monkeypatch, client)
    summary = _layer(client).summarize(
        metric="actual_load_mwh",
        area="DE",
        start=datetime(2026, 6, 8, tzinfo=UTC),
        end=datetime(2026, 6, 8, 1, tzinfo=UTC),
        release_id="seed-2026-06-08-b",
    )
    assert (summary.count, summary.minimum, summary.maximum, summary.unit) == (1, 12.0, 12.0, "MWh")


def test_bytes_cap_and_timeout_fail_closed(monkeypatch):
    class FakeBadRequest(Exception):
        pass

    client = FakeBigQueryClient(fail_with=FakeBadRequest("bytes billed limit exceeded"))
    _install_fake_bigquery(monkeypatch, client, bad_request=FakeBadRequest)
    with pytest.raises(ValidationError) as excinfo:
        _layer(client).resolve_release("actual_load_mwh")
    assert excinfo.value.code == "query_rejected"


def test_statement_timeout_fails_closed(monkeypatch):
    class FakeJobTimeout:
        def result(self, timeout=None):
            raise concurrent.futures.TimeoutError()

    class TimeoutClient(FakeBigQueryClient):
        def query(self, sql, job_config=None, timeout=None):
            self.calls.append((sql, job_config, timeout))
            return FakeJobTimeout()

    client = TimeoutClient()
    _install_fake_bigquery(monkeypatch, client)
    with pytest.raises(ValidationError) as excinfo:
        _layer(client).resolve_release("actual_load_mwh")
    assert excinfo.value.code == "query_rejected"
