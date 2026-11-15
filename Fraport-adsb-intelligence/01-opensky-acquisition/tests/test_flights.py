from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pyarrow.parquet as pq
import pytest

from opensky_ingest import cli
from opensky_ingest.errors import SourceError
from opensky_ingest.fetch import InjectedCrash
from opensky_ingest.flights import collect_flight_day, collect_flight_range
from opensky_ingest.manifest import flight_manifest_rel, flight_parquet_rel
from opensky_ingest.query import flight_sql
from opensky_ingest.schema import FLIGHT_COLUMNS, FLIGHT_TRINO_TYPES
from opensky_ingest.util import day_epoch
from tests.test_collect import HourCursor

DAY = date(2026, 10, 12)
NEXT = date(2026, 10, 13)
STAMP = day_epoch(DAY)


def sample_flight(
    icao: str = "abc123",
    firstseen: int | None = None,
    departure: str = "EDDF",
    arrival: str = "LOWW",
    day: int | None = None,
) -> tuple:
    seen = STAMP + 100 if firstseen is None else firstseen
    return (
        icao,
        seen,
        departure,
        seen + 3600,
        arrival,
        "DLH123  ",
        [(seen, 50.0, 8.6, 300.0, 90.0, False)],
        1000,
        100,
        2000,
        200,
        1,
        1,
        [("EDDF", 1000, 100)],
        [("LOWW", 2000, 200)],
        STAMP if day is None else day,
    )


class FlightSource:
    def __init__(
        self,
        rows: list[tuple],
        *,
        global_exists: bool = True,
        columns: list[tuple[str, str]] | None = None,
        fail: bool = False,
    ) -> None:
        self.rows = rows
        self.global_exists = global_exists
        self.columns = columns or list(FLIGHT_TRINO_TYPES.items())
        self.fail = fail
        self.queries: list[str] = []
        self.stats = {"processedBytes": 2_000_000}
        self.query_id = "q-flight"

    def cursor(self) -> HourCursor:
        return HourCursor(self)  # type: ignore[arg-type]

    def close(self) -> None:
        pass

    def handle(self, sql: str):
        self.queries.append(sql)
        if sql.startswith("DESCRIBE"):
            return [("Column",)], [(name, typ, "", "") for name, typ in self.columns]
        if sql.startswith("SELECT 1 FROM"):
            return [("_col0",)], ([(1,)] if self.global_exists else [])
        if sql.startswith("SELECT"):
            if self.fail:
                raise SourceError("QUERY_FAILED")
            return [(name,) for name in FLIGHT_COLUMNS], list(self.rows)
        raise AssertionError(sql)


def manifest_path(cfg, day: date = DAY):
    return cfg.paths.data_root / flight_manifest_rel(day)


def parquet_path(cfg, day: date = DAY):
    return cfg.paths.data_root / flight_parquet_rel("EDDF", "v1", day)


def test_sql_filters_the_airport_and_keeps_nested_columns(cfg):
    sql = flight_sql(cfg, DAY)
    assert f"day = {STAMP}" in sql
    assert "estdepartureairport = 'EDDF'" in sql
    assert "estarrivalairport = 'EDDF'" in sql
    assert "track" in sql
    assert "otherarrivalairportcandidates" in sql


def test_commit_and_repeat_does_not_change_the_manifest(cfg):
    result = collect_flight_day(FlightSource([sample_flight()]), cfg, DAY, pause_seconds=0)
    assert result["outcome"] == "committed"
    assert result["rows"] == 1
    assert result["departures"] == 1
    assert result["arrivals"] == 0
    assert result["dataset_id"] == "eddf_flights"
    digest = manifest_path(cfg).read_bytes()
    track = pq.read_table(parquet_path(cfg)).column("track")
    assert track[0].as_py()[0]["latitude"] == 50.0
    again = collect_flight_day(
        FlightSource([sample_flight(icao="other")]), cfg, DAY, pause_seconds=0
    )
    assert again["outcome"] == "skipped"
    assert manifest_path(cfg).read_bytes() == digest


def test_duplicate_flights_are_counted(cfg):
    rows = [sample_flight(), sample_flight()]
    result = collect_flight_day(FlightSource(rows), cfg, DAY, pause_seconds=0)
    assert result["duplicate_key_rows"] == 1
    assert result["rows"] == 2


def test_row_for_another_airport_is_not_committed(cfg):
    result = collect_flight_day(
        FlightSource([sample_flight(departure="LOWW", arrival="EDDM")]),
        cfg,
        DAY,
        pause_seconds=0,
    )
    assert result["error_class"] == "VALIDATION"
    assert not manifest_path(cfg).exists()


def test_empty_day_when_the_global_partition_has_rows(cfg):
    result = collect_flight_day(FlightSource([], global_exists=True), cfg, DAY, pause_seconds=0)
    assert result["status"] == "empty"
    assert not parquet_path(cfg).exists()
    assert manifest_path(cfg).exists()


def test_missing_source_day_is_failed_not_committed(cfg):
    result = collect_flight_day(FlightSource([], global_exists=False), cfg, DAY, pause_seconds=0)
    assert result["error_class"] == "SOURCE_MISSING"
    assert not manifest_path(cfg).exists()


def test_empty_partition_on_a_gap_day_is_a_source_gap(cfg):
    day = date(2026, 1, 2)
    result = collect_flight_day(FlightSource([], global_exists=False), cfg, day, pause_seconds=0)
    assert result["outcome"] == "committed"
    assert result["status"] == "source_gap"
    assert "known_gap_overlap" in result["flags"]
    assert not parquet_path(cfg, day).exists()
    assert manifest_path(cfg, day).exists()


def test_crash_after_publish_is_redone_without_leaving_the_orphan(cfg):
    source = FlightSource([sample_flight()])
    with pytest.raises(InjectedCrash):
        collect_flight_day(source, cfg, DAY, run_id="r1", crash_after="published", pause_seconds=0)
    assert parquet_path(cfg).exists()
    assert not manifest_path(cfg).exists()
    result = collect_flight_day(source, cfg, DAY, run_id="r2", pause_seconds=0)
    assert result["outcome"] == "committed"
    assert list((cfg.paths.data_root / "quarantine").rglob("*.parquet"))


def test_schema_drift_stops_the_run(cfg):
    columns = [(name, typ) for name, typ in FLIGHT_TRINO_TYPES.items() if name != "track"]
    with pytest.raises(Exception, match="SCHEMA_DRIFT"):
        collect_flight_day(
            FlightSource([sample_flight()], columns=columns), cfg, DAY, pause_seconds=0
        )
    assert not manifest_path(cfg).exists()


def test_range_stops_on_a_failed_day(cfg):
    summary = collect_flight_range(
        FlightSource([sample_flight()], fail=True),
        cfg,
        DAY,
        DAY + timedelta(days=2),
        pause_seconds=0,
        max_duration=timedelta(hours=1),
    )
    assert summary["outcome"] == "stopped"
    assert summary["reason"] == "day_failed"
    assert summary["committed"] == 0
    assert summary["next_day"] == "2026-10-12"
    assert not manifest_path(cfg, NEXT).exists()


def test_cli_collect_flights(cfg, capsys, monkeypatch):
    monkeypatch.setattr(cli, "ensure_free_disk", lambda _cfg: None)
    code = cli.main(
        ["collect-flights", "--from", "2026-10-12", "--until", "2026-10-13"],
        connection_factory=lambda _cfg, interactive: FlightSource([sample_flight()]),
    )
    assert code == 0
    output = capsys.readouterr().out
    assert "outcome: committed" in output
    assert "flights outcome: finished" in output
    assert "committed: 1" in output


def test_day_inside_a_documented_gap():
    from opensky_ingest.reference import day_gap_status, load_gaps

    inside = day_gap_status(load_gaps(), datetime(2023, 1, 19, tzinfo=UTC))
    overlap = day_gap_status(load_gaps(), datetime(2026, 1, 3, tzinfo=UTC))
    clear = day_gap_status(load_gaps(), datetime(2026, 10, 12, tzinfo=UTC))
    assert inside == "inside"
    assert overlap == "overlap"
    assert clear == "none"
