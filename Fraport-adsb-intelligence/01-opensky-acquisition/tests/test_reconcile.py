from __future__ import annotations

from datetime import timedelta

from opensky_ingest import cli
from opensky_ingest.fetch import collect_hour
from opensky_ingest.reconcile import reconcile_hours
from opensky_ingest.util import epoch
from tests.test_collect import HOUR, HourCursor, HourSource, sample_row


class AggregateSource:
    def __init__(self, rows: int, aircraft: int, low: int | None, high: int | None) -> None:
        self.rows = rows
        self.aircraft = aircraft
        self.low = low
        self.high = high
        self.queries: list[str] = []
        self.stats = {"processedBytes": 1_000}
        self.query_id = "q-reconcile"

    def cursor(self) -> HourCursor:
        return HourCursor(self)  # type: ignore[arg-type]

    def close(self) -> None:
        pass

    def handle(self, sql: str):
        self.queries.append(sql)
        if "count(*)" not in sql:
            raise AssertionError(sql)
        return [("c",)], [(self.rows, self.aircraft, 0, self.low, self.high)]


def test_reconcile_matches_the_file(cfg):
    collect_hour(HourSource([sample_row()]), cfg, HOUR, pause_seconds=0)
    stamp = epoch(HOUR)
    result = reconcile_hours(
        AggregateSource(1, 1, stamp, stamp),
        cfg,
        HOUR,
        HOUR + timedelta(hours=1),
        pause_seconds=0,
    )
    assert result["outcome"] == "matched"
    assert result["matched"] == 1
    assert result["mismatched"] == 0
    assert (cfg.paths.data_root / "reports" / "reconcile" / f"{result['run_id']}.json").exists()


def test_reconcile_records_a_source_count_mismatch(cfg):
    collect_hour(HourSource([sample_row()]), cfg, HOUR, pause_seconds=0)
    stamp = epoch(HOUR)
    result = reconcile_hours(
        AggregateSource(2, 1, stamp, stamp),
        cfg,
        HOUR,
        HOUR + timedelta(hours=1),
        pause_seconds=0,
    )
    assert result["outcome"] == "mismatched"
    assert result["hours"][0]["mismatches"] == ["rows"]


def test_reconcile_records_a_missing_manifest(cfg):
    result = reconcile_hours(
        AggregateSource(0, 0, None, None),
        cfg,
        HOUR,
        HOUR + timedelta(hours=1),
        pause_seconds=0,
    )
    assert result["hours"][0]["mismatches"] == ["missing_manifest"]
    assert result["hours"][0]["match"] is False


def test_reconcile_stops_at_the_duration_limit(cfg):
    times = iter([0.0, 10.0])
    result = reconcile_hours(
        AggregateSource(0, 0, None, None),
        cfg,
        HOUR,
        HOUR + timedelta(hours=2),
        pause_seconds=0,
        max_duration=timedelta(seconds=10),
        clock=lambda: next(times),
    )
    assert result["outcome"] == "stopped"
    assert result["reason"] == "max_duration"
    assert result["checked"] == 0
    assert result["next_hour"] == "2026-10-15T12:00:00Z"


def test_cli_reconcile_matches(cfg, capsys):
    collect_hour(HourSource([sample_row()]), cfg, HOUR, pause_seconds=0)
    stamp = epoch(HOUR)
    code = cli.main(
        ["reconcile", "--from", "2026-10-15T12:00:00Z", "--until", "2026-10-15T13:00:00Z"],
        connection_factory=lambda _cfg, interactive: AggregateSource(1, 1, stamp, stamp),
    )
    assert code == 0
    assert "reconcile outcome: matched" in capsys.readouterr().out
