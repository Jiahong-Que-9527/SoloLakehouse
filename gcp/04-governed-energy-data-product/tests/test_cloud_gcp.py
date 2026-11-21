"""Cloud adapter contract tests for the publication path.

The fakes mirror exactly the slice of the real client that
BigQueryProductStore uses, in the G01/G03 test style. The decisive test
runs the FULL publisher flow against the fake-backed adapter — that is
the integration the first live drill proved missing.
"""

import sys
import types
from datetime import UTC, date, datetime, timedelta

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
            if "LIMIT 1" in sql:
                # Latest ledger row wins: the ledger is append-only.
                release_id = job_config.query_parameters[1].value
                history = sorted(
                    (row for row in matching if row["release_id"] == release_id),
                    key=lambda row: row["published_at"],
                    reverse=True,
                )
                return FakeJob(history[:1])
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
        return types.SimpleNamespace(
            table_id=table, description=self.tables.get(table), view_query=None
        )

    def update_table(self, table, fields):
        self.updates.append((table.table_id, fields))
        if "view_query" in fields:
            # Behave like BigQuery: the view definition becomes the query.
            self.view_definition = table.view_query
        return table

    def insert_rows_json(self, table, rows):
        self.inserted.setdefault(table, []).extend(rows)
        if table.endswith(".release"):
            # Streaming inserts are readable back, and the TIMESTAMP column
            # round-trips as an aware datetime, as the real API returns it.
            self.release_rows.extend(
                {**row, "published_at": datetime.fromisoformat(row["published_at"])} for row in rows
            )
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
    # No top-level bigquery.NotFound: the real library surfaces it as
    # google.api_core.exceptions.NotFound, and the fake must mirror that —
    # the third live execution crashed on exactly this divergence.
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
    # The real G01 ledger types the window as DATE: the client returns
    # datetime.date, not datetime — publish_job must coerce (see the
    # expected-grid regression test below).
    "window_start": date(2026, 6, 8),
    "window_end": date(2026, 6, 15),
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
    # The view switch went through the tables API: the view sits in the
    # dataset access entries, so DDL CREATE OR REPLACE would demand
    # bigquery.datasets.update (the fourth live execution's 403).
    assert any(
        table_id.endswith("energy_load_current") and fields == ["view_query"]
        for table_id, fields in client.updates
    )
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
    # The withdrawal APPENDED a superseding ledger row: the ledger is
    # append-only evidence, and DML cannot touch streaming-buffered rows
    # (the live drill's 400).
    inserted = client.inserted.get("test-project.energy_product.release", [])
    assert any(
        row["release_id"] == GOOD_CANDIDATE and row["status"] == "withdrawn" for row in inserted
    )
    # The current view was replaced by the zero-row placeholder, through
    # the tables API like every view switch.
    assert client.view_definition is not None and "WHERE FALSE" in client.view_definition


def test_current_release_id_parses_the_pointer_from_the_view_definition(monkeypatch):
    store, client = _store(monkeypatch)
    assert store.current_release_id("energy_load") is None
    client.view_definition = (
        f"SELECT * FROM `test-project.energy_product.energy_load_v{GOOD_CANDIDATE}`"
    )
    assert store.current_release_id("energy_load") == GOOD_CANDIDATE


def test_the_ledger_is_append_only_and_reads_latest_wins(monkeypatch):
    """A status change appends a superseding row at a new timestamp and
    reads back as the release's single current status: the streaming
    buffer forbids DML on freshly inserted rows, so the withdrawal drill
    caught the original UPDATE attempt with a 400."""
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
    original = store.release_row("energy_load", GOOD_CANDIDATE)

    # A withdrawal happens after the publication — latest-wins needs a
    # strictly later timestamp.
    withdrawn_at = META["evaluation_time"] + timedelta(hours=1)
    store.mark_release_status("energy_load", GOOD_CANDIDATE, "withdrawn", withdrawn_at)

    latest = store.release_row("energy_load", GOOD_CANDIDATE)
    assert latest.status == "withdrawn"
    assert latest.published_at == withdrawn_at
    assert latest.checksum == original.checksum
    # releases() still yields one row per release id.
    assert [row.release_id for row in store.releases("energy_load")] == [GOOD_CANDIDATE]
    # The ledger kept the original passed row as history.
    inserted = client.inserted["test-project.energy_product.release"]
    assert [row["status"] for row in inserted] == ["passed", "withdrawn"]


def test_fetch_input_release_reads_the_g01_ledger_and_rows(monkeypatch):
    store, client = _store(monkeypatch)
    ledger, fetched = store.fetch_input_release(GOOD_INPUT_RELEASE)
    assert ledger["release_id"] == GOOD_INPUT_RELEASE
    assert len(fetched) == 672
    with pytest.raises(LookupError, match="not found"):
        store.fetch_input_release("missing")


def test_expected_grid_survives_date_typed_ledger_windows():
    """Regression for the first live publication (blocked 2026-11-21): the
    G01 ledger types the window as DATE, the client returns datetime.date,
    and date arithmetic truncated 672 quarter-hour keys onto 7 day keys —
    completeness failed with "missing 7, unexpected 672" on healthy data.
    G01's window dates are Europe/Berlin local midnights, so the June week
    06-08..06-15 spans 2026-06-07 22:00..2026-06-14 22:00 UTC in the data."""
    from energy_product.publish_job import _expected_grid

    starts = [
        datetime(2026, 6, 7, 22, 0, tzinfo=UTC) + timedelta(minutes=15 * index)
        for index in range(672)
    ]
    rows = [
        {"area": "DE", "metric": "actual_load_mwh", "interval_start": start} for start in starts
    ]
    grid = _expected_grid(date(2026, 6, 8), date(2026, 6, 15), rows, interval_minutes=15)
    assert grid == [("DE", "actual_load_mwh", start) for start in starts]
    # Date-only ISO strings and aware datetimes coerce to the same grid.
    assert _expected_grid("2026-06-08", "2026-06-15", rows, interval_minutes=15) == grid
    assert (
        _expected_grid(
            datetime(2026, 6, 7, 22, 0, tzinfo=UTC),
            datetime(2026, 6, 14, 22, 0, tzinfo=UTC),
            rows,
            15,
        )
        == grid
    )


def test_expected_grid_counts_dst_shifted_berlin_windows_correctly():
    """G01 windows cross DST: a Berlin week containing the spring-forward
    night spans 167 UTC hours (668 intervals), the autumn-back week 169
    hours (676). The grid must follow the zone-converted bounds."""
    from energy_product.publish_job import _expected_grid

    def rows_from(start: datetime, count: int) -> list[dict]:
        return [
            {
                "area": "DE",
                "metric": "actual_load_mwh",
                "interval_start": start + timedelta(minutes=15 * index),
            }
            for index in range(count)
        ]

    # Spring-forward: 2026-03-29 02:00 local becomes 03:00 (CEST).
    spring = rows_from(datetime(2026, 3, 22, 23, 0, tzinfo=UTC), 668)
    assert len(_expected_grid(date(2026, 3, 23), date(2026, 3, 30), spring, 15)) == 668
    # Autumn-back: 2026-10-25 03:00 local becomes 02:00 (CET).
    autumn = rows_from(datetime(2026, 10, 18, 22, 0, tzinfo=UTC), 676)
    assert len(_expected_grid(date(2026, 10, 19), date(2026, 10, 26), autumn, 15)) == 676


def test_expected_grid_stays_independent_of_the_actual_rows():
    """A duplicate masking a missing interval must not shrink or shift the
    expected grid: expectations come from the window, not the data."""
    from energy_product.fixture import expected_grid as fixture_grid
    from energy_product.fixture import with_duplicate_masking_missing
    from energy_product.publish_job import _expected_grid

    grid = fixture_grid()
    rows = with_duplicate_masking_missing(
        [
            {"area": area, "metric": metric, "interval_start": start, "interval_end": start}
            for area, metric, start in grid
        ]
    )
    assert (
        _expected_grid(
            datetime(2026, 6, 8, tzinfo=UTC), datetime(2026, 6, 15, tzinfo=UTC), rows, 15
        )
        == grid
    )
