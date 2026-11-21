"""Cloud adapter contract tests for the publication path.

The fakes mirror exactly the slice of the real client that
BigQueryProductStore uses, in the G01/G03 test style. The decisive test
runs the FULL publisher flow against the fake-backed adapter — that is
the integration the first live drill proved missing.
"""

import sys
import types
from datetime import UTC, datetime

import pytest

from conftest import load_contracts
from energy_product.cloud_gcp import BigQueryProductStore
from energy_product.fixture import (
    GOOD_CANDIDATE,
    GOOD_INPUT_RELEASE,
    candidate_metadata,
    candidate_rows,
    expected_grid,
    with_duplicate_masking_missing,
)
from energy_product.publisher import PublishRequest, publish, withdraw

CONTRACT, _, _ = load_contracts()
GRID = expected_grid()
ROWS = candidate_rows(GRID)
META = candidate_metadata()


class FakeJob:
    def __init__(self, rows=None):
        self._rows = rows or []

    def result(self):
        return iter(self._rows)


class FakeBigQueryClient:
    project = "test-project"

    def __init__(self):
        self.ledger = []
        self.input_rows = []
        self.release_rows = []  # dicts as stored via insert_rows_json
        self.view_definition = None
        self.tables = {}  # table_id -> description
        self.queries = []
        self.inserted = {}
        self.updates = []

    def query(self, sql, job_config=None):
        self.queries.append((sql, job_config))
        if sql.startswith("CREATE OR REPLACE VIEW"):
            # Behave like BigQuery: the view definition becomes the SELECT.
            self.view_definition = sql.split(" AS ", 1)[1]
            return FakeJob()
        if "FROM `test-project.energy.load_release`" in sql:
            release_id = job_config.query_parameters[0].value
            matches = [row for row in self.ledger if row["release_id"] == release_id]
            return FakeJob(matches)
        if "FROM `test-project.energy.metric_observation`" in sql:
            return FakeJob(self.input_rows)
        if "FROM `test-project.energy_product.release`" in sql:
            product = job_config.query_parameters[0].value
            matching = [row for row in self.release_rows if row["product"] == product]
            if "ORDER BY published_at" in sql:
                return FakeJob(matching)
            release_id = job_config.query_parameters[1].value
            return FakeJob([row for row in matching if row["release_id"] == release_id])
        if "INFORMATION_SCHEMA.VIEWS" in sql:
            if self.view_definition is None:
                return FakeJob([])
            return FakeJob([{"view_definition": self.view_definition}])
        if "SELECT * FROM `test-project.energy_product.energy_load_current`" in sql:
            return FakeJob(self.current_select_rows)
        return FakeJob()

    current_select_rows = []

    def load_table_from_file(self, stream, destination, job_config=None):
        if stream.tell() != 0:
            raise ValueError("stream must start at position 0")
        self.loaded = (stream.read(), destination, job_config)
        return FakeJob()

    def get_table(self, table):
        return types.SimpleNamespace(table_id=table, description=self.tables.get(table))

    def update_table(self, table, fields):
        self.updates.append((table.table_id, fields))
        return table

    def insert_rows_json(self, table, rows):
        self.inserted.setdefault(table, []).extend(rows)
        return []


class FakeScalarQueryParameter:
    def __init__(self, name, type_, value):
        self.name = name
        self.type_ = type_
        self.value = value


def _install_fake_bigquery(monkeypatch, client):
    google = types.ModuleType("google")
    cloud = types.ModuleType("google.cloud")
    bigquery = types.ModuleType("google.cloud.bigquery")

    class NotFound(Exception):
        pass

    bigquery.Client = lambda: client
    bigquery.QueryJobConfig = lambda **kwargs: types.SimpleNamespace(**kwargs)
    bigquery.ScalarQueryParameter = FakeScalarQueryParameter
    bigquery.LoadJobConfig = lambda **kwargs: types.SimpleNamespace(**kwargs)
    bigquery.SourceFormat = types.SimpleNamespace(PARQUET="PARQUET")
    bigquery.WriteDisposition = types.SimpleNamespace(WRITE_EMPTY="WRITE_EMPTY")
    bigquery.NotFound = NotFound
    api_core = types.ModuleType("google.api_core")
    exceptions = types.ModuleType("google.api_core.exceptions")
    exceptions.NotFound = NotFound
    api_core.exceptions = exceptions
    google.cloud = cloud
    google.api_core = api_core
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud)
    monkeypatch.setitem(sys.modules, "google.cloud.bigquery", bigquery)
    monkeypatch.setitem(sys.modules, "google.api_core", api_core)
    monkeypatch.setitem(sys.modules, "google.api_core.exceptions", exceptions)


LEDGER_ROW = {
    "release_id": GOOD_INPUT_RELEASE,
    "window_start": datetime(2026, 6, 8, tzinfo=UTC),
    "window_end": datetime(2026, 6, 15, tzinfo=UTC),
    "input_checksum": "deadbeef",
    "row_count": 672,
    "git_sha": "abc1234",
    "quality_status": "passed",
    "published_at": datetime(2026, 6, 15, 1, 0, tzinfo=UTC),
}


def _store(monkeypatch):
    client = FakeBigQueryClient()
    client.ledger = [LEDGER_ROW]
    client.input_rows = ROWS
    _install_fake_bigquery(monkeypatch, client)
    return BigQueryProductStore("energy_product", client=client), client


def test_full_publish_flow_runs_against_the_fake_backed_adapter(monkeypatch):
    """The integration the first live drill proved missing: the publisher
    port drives the BigQuery adapter end to end."""
    store, client = _store(monkeypatch)

    request = PublishRequest(
        product=CONTRACT.slug,
        candidate_id=GOOD_CANDIDATE,
        input_release_id=GOOD_INPUT_RELEASE,
        contract=CONTRACT,
        rows=ROWS,
        expected_grid=GRID,
        ingested_at=META["ingested_at"],
        evaluation_time=META["evaluation_time"],
        git_sha="abc1234",
        approver="owner",
        approved=True,
    )
    result = publish(store, request)

    assert result.status == "passed"
    assert store.current_release_id("energy_load") == GOOD_CANDIDATE
    # The version table carries the checksum in its description.
    assert client.updates[0][1] == ["description"]
    # The ledger row holds the manifest as canonical JSON.
    ledger_rows = client.inserted["test-project.energy_product.release"]
    assert ledger_rows[0]["status"] == "passed"
    assert '"input_release_id"' in ledger_rows[0]["manifest"]


def test_blocked_candidate_writes_quarantine_and_keeps_the_previous_release(monkeypatch):
    store, _ = _store(monkeypatch)
    request = PublishRequest(
        product=CONTRACT.slug,
        candidate_id=GOOD_CANDIDATE,
        input_release_id=GOOD_INPUT_RELEASE,
        contract=CONTRACT,
        rows=ROWS,
        expected_grid=GRID,
        ingested_at=META["ingested_at"],
        evaluation_time=META["evaluation_time"],
        approved=True,
    )
    publish(store, request)

    blocked = publish(
        store,
        PublishRequest(
            product=CONTRACT.slug,
            candidate_id="cand-bad",
            input_release_id=GOOD_INPUT_RELEASE,
            contract=CONTRACT,
            rows=with_duplicate_masking_missing(ROWS),
            expected_grid=GRID,
            ingested_at=META["ingested_at"],
            evaluation_time=META["evaluation_time"],
            approved=True,
        ),
    )
    assert blocked.status == "blocked"
    assert store.current_release_id("energy_load") == GOOD_CANDIDATE
    quarantine_rows = store.insert_quarantine_rows and client_quarantine(store)
    assert quarantine_rows


def client_quarantine(store):
    client = store._bigquery()
    return client.inserted.get("test-project.energy_product.quarantine", [])


def test_withdraw_falls_back_to_an_empty_authorised_view(monkeypatch):
    store, client = _store(monkeypatch)
    request = PublishRequest(
        product=CONTRACT.slug,
        candidate_id=GOOD_CANDIDATE,
        input_release_id=GOOD_INPUT_RELEASE,
        contract=CONTRACT,
        rows=ROWS,
        expected_grid=GRID,
        ingested_at=META["ingested_at"],
        evaluation_time=META["evaluation_time"],
        approved=True,
    )
    publish(store, request)
    # Simulate the view definition the real CREATE OR REPLACE produces.
    client.view_definition = (
        f"SELECT * FROM `test-project.energy_product.energy_load_v{GOOD_CANDIDATE}`"
    )

    fallback = withdraw(store, CONTRACT, operator="owner", at=META["evaluation_time"])

    assert fallback is None
    # The withdrawn release's status was flipped in the ledger.
    updates = client.queries
    assert any("SET status = @status" in sql for sql, _ in updates)
    # The current view was replaced by the zero-row placeholder.
    assert any("WHERE FALSE" in sql for sql, _ in updates)


def test_current_release_id_parses_the_pointer_from_the_view_definition(monkeypatch):
    store, client = _store(monkeypatch)
    assert store.current_release_id("energy_load") is None
    client.view_definition = (
        f"SELECT * FROM `test-project.energy_product.energy_load_v{GOOD_CANDIDATE}`"
    )
    assert store.current_release_id("energy_load") == GOOD_CANDIDATE


def test_fetch_input_release_reads_the_g01_ledger_and_rows(monkeypatch):
    store, client = _store(monkeypatch)
    ledger, fetched = store.fetch_input_release(GOOD_INPUT_RELEASE)
    assert ledger["release_id"] == GOOD_INPUT_RELEASE
    assert len(fetched) == 672
    with pytest.raises(LookupError, match="not found"):
        store.fetch_input_release("missing")
