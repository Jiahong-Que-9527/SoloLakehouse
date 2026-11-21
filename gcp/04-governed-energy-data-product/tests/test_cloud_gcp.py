"""Cloud adapter contract tests for the publication path.

The fakes mirror exactly the slice of the real client that
BigQueryProductStore uses, in the G01/G03 test style. SQL semantics are
proven against the live service during cloud verification; these tests
pin the wiring: the producer reads the G01 ledger and rows, the version
table is a WRITE_EMPTY parquet load, the view is one CREATE OR REPLACE
statement, and the ledger/quarantine inserts reject nothing silently.
"""

import sys
import types
from datetime import UTC, datetime

import pytest

from conftest import GOOD_CANDIDATE
from energy_product.cloud_gcp import BigQueryProductStore
from energy_product.fixture import candidate_rows, expected_grid
from energy_product.store import ReleaseRow


class FakeJob:
    def __init__(self, rows=None):
        self._rows = rows or []

    def result(self):
        return iter(self._rows)


class FakeBigQueryClient:
    project = "test-project"

    def __init__(self, ledger=None, input_rows=None, release_rows=None):
        self.ledger = ledger or []
        self.input_rows = input_rows or []
        self.release_rows = release_rows or []
        self.queries = []  # (sql, job_config)
        self.loaded = []  # (payload, destination, job_config)
        self.inserted = {}
        self.get_table_calls = []
        self.fail_get_table = True

    def query(self, sql, job_config=None):
        self.queries.append((sql, job_config))
        if "FROM `test-project.energy.load_release`" in sql:
            return FakeJob(self.ledger)
        if "FROM `test-project.energy.metric_observation`" in sql:
            return FakeJob(self.input_rows)
        if "FROM `test-project.energy_product.release`" in sql:
            return FakeJob(self.release_rows)
        return FakeJob()

    def load_table_from_file(self, stream, destination, job_config=None):
        if stream.tell() != 0:
            raise ValueError("stream must start at position 0")
        self.loaded.append((stream.read(), destination, job_config))
        return FakeJob()

    def get_table(self, table):
        self.get_table_calls.append(table)
        if self.fail_get_table:
            raise _not_found()
        return types.SimpleNamespace(table_id=table)

    def insert_rows_json(self, table, rows):
        self.inserted.setdefault(table, []).extend(rows)
        return []


class FakeScalarQueryParameter:
    def __init__(self, name, type_, value):
        self.name = name
        self.type_ = type_
        self.value = value


class FakeNotFound(Exception):
    """One shared NotFound class so the adapter's except clause matches."""


def _not_found():
    return FakeNotFound()


def _install_fake_bigquery(monkeypatch, client):
    google = types.ModuleType("google")
    cloud = types.ModuleType("google.cloud")
    bigquery = types.ModuleType("google.cloud.bigquery")
    api_core = types.ModuleType("google.api_core")
    exceptions = types.ModuleType("google.api_core.exceptions")

    bigquery.NotFound = FakeNotFound
    bigquery.Client = lambda: client
    bigquery.QueryJobConfig = lambda **kwargs: types.SimpleNamespace(**kwargs)
    bigquery.ScalarQueryParameter = FakeScalarQueryParameter
    bigquery.LoadJobConfig = lambda **kwargs: types.SimpleNamespace(**kwargs)
    bigquery.SourceFormat = types.SimpleNamespace(PARQUET="PARQUET")
    bigquery.WriteDisposition = types.SimpleNamespace(WRITE_EMPTY="WRITE_EMPTY")
    api_core.exceptions = exceptions
    google.cloud = cloud
    google.api_core = api_core
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud)
    monkeypatch.setitem(sys.modules, "google.cloud.bigquery", bigquery)
    monkeypatch.setitem(sys.modules, "google.api_core", api_core)
    monkeypatch.setitem(sys.modules, "google.api_core.exceptions", exceptions)


LEDGER_ROW = {
    "release_id": "input-week-672",
    "window_start": datetime(2026, 6, 8, tzinfo=UTC),
    "window_end": datetime(2026, 6, 15, tzinfo=UTC),
    "input_checksum": "deadbeef",
    "row_count": 672,
    "git_sha": "abc1234",
    "quality_status": "passed",
    "published_at": datetime(2026, 6, 15, 1, 0, tzinfo=UTC),
}


def _release_row():
    return ReleaseRow(
        product="energy_load",
        release_id=GOOD_CANDIDATE,
        input_release_id="input-week-672",
        contract_version="1.0.0",
        status="passed",
        output_table=f"energy_load_v{GOOD_CANDIDATE}",
        git_sha="abc1234",
        approver="owner",
        checksum="cafe",
        published_at=datetime(2026, 6, 15, 2, 0, tzinfo=UTC),
        manifest={"product": "energy_load"},
    )


def test_fetch_input_release_reads_the_g01_ledger_and_rows(monkeypatch):
    rows = candidate_rows(expected_grid())
    client = FakeBigQueryClient(ledger=[LEDGER_ROW], input_rows=rows)
    _install_fake_bigquery(monkeypatch, client)
    store = BigQueryProductStore("energy_product", client=client)

    ledger, fetched = store.fetch_input_release("test-project", "input-week-672")

    assert ledger["release_id"] == "input-week-672"
    assert len(fetched) == 672
    (ledger_sql, config), (rows_sql, _) = client.queries
    assert "FROM `test-project.energy.load_release`" in ledger_sql
    assert "FROM `test-project.energy.metric_observation`" in rows_sql
    assert config.query_parameters[0].value == "input-week-672"


def test_fetch_input_release_of_an_unknown_id_is_a_lookup_error(monkeypatch):
    client = FakeBigQueryClient(ledger=[])
    _install_fake_bigquery(monkeypatch, client)
    store = BigQueryProductStore("energy_product", client=client)
    with pytest.raises(LookupError, match="not found"):
        store.fetch_input_release("test-project", "missing")


def test_write_version_table_loads_parquet_with_write_empty(monkeypatch):
    client = FakeBigQueryClient()
    _install_fake_bigquery(monkeypatch, client)
    store = BigQueryProductStore("energy_product", client=client)

    store.write_version_table(
        "test-project", "energy_load", GOOD_CANDIDATE, candidate_rows(expected_grid())
    )

    ((payload, destination, job_config),) = client.loaded
    assert destination == f"test-project.energy_product.energy_load_v{GOOD_CANDIDATE}"
    assert job_config.write_disposition == "WRITE_EMPTY"
    assert len(payload) > 0


def test_point_current_view_is_one_create_or_replace(monkeypatch):
    client = FakeBigQueryClient()
    _install_fake_bigquery(monkeypatch, client)
    store = BigQueryProductStore("energy_product", client=client)

    store.point_current_view("test-project", "energy_load", GOOD_CANDIDATE)

    (sql, _) = client.queries[0]
    assert sql.startswith(
        "CREATE OR REPLACE VIEW `test-project.energy_product.energy_load_current`"
    )
    assert f"FROM `test-project.energy_product.energy_load_v{GOOD_CANDIDATE}`" in sql


def test_empty_current_view_selects_false_over_the_schema_table(monkeypatch):
    client = FakeBigQueryClient()
    _install_fake_bigquery(monkeypatch, client)
    store = BigQueryProductStore("energy_product", client=client)

    store.empty_current_view("test-project", "energy_load", f"energy_load_v{GOOD_CANDIDATE}")

    (sql, _) = client.queries[0]
    assert "WHERE FALSE" in sql
    assert f"FROM `test-project.energy_product.energy_load_v{GOOD_CANDIDATE}`" in sql


def test_release_row_and_quarantine_inserts_go_to_the_ledger_tables(monkeypatch):
    client = FakeBigQueryClient()
    _install_fake_bigquery(monkeypatch, client)
    store = BigQueryProductStore("energy_product", client=client)

    store.insert_release_row("test-project", _release_row())
    store.insert_quarantine_rows(
        "test-project",
        [
            {
                "product": "energy_load",
                "release_id": "cand-bad",
                "input_release_id": "input-week-672",
                "check": "completeness",
                "detail": "missing 1",
                "offending": [("DE", "actual_load_mwh", "x")],
                "recorded_at": datetime(2026, 6, 15, 2, 0, tzinfo=UTC),
            }
        ],
    )

    ledger_rows = client.inserted["test-project.energy_product.release"]
    assert ledger_rows[0]["status"] == "passed"
    assert '"product":"energy_load"' in ledger_rows[0]["manifest"]
    quarantine_rows = client.inserted["test-project.energy_product.quarantine"]
    assert quarantine_rows[0]["check"] == "completeness"


def test_mark_release_status_is_one_update_statement(monkeypatch):
    client = FakeBigQueryClient()
    _install_fake_bigquery(monkeypatch, client)
    store = BigQueryProductStore("energy_product", client=client)

    store.mark_release_status("test-project", "energy_load", GOOD_CANDIDATE, "withdrawn")

    (sql, config) = client.queries[0]
    assert sql.startswith("UPDATE `test-project.energy_product.release` SET status = @status")
    assert config.query_parameters[0].value == "withdrawn"


def test_version_table_exists_probes_the_table_api(monkeypatch):
    client = FakeBigQueryClient()
    _install_fake_bigquery(monkeypatch, client)
    store = BigQueryProductStore("energy_product", client=client)

    assert store.version_table_exists("energy_load", GOOD_CANDIDATE) is False
    client.fail_get_table = False
    assert store.version_table_exists("energy_load", GOOD_CANDIDATE) is True
