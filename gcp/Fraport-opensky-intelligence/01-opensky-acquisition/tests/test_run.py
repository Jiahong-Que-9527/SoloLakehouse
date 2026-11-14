from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from opensky_ingest import cli
from opensky_ingest.errors import AuthRequired, SourceError
from opensky_ingest.manifest import hour_manifest_rel
from opensky_ingest.run import collect_range, parse_duration
from opensky_ingest.schema import STATE_VECTOR_COLUMNS
from opensky_ingest.util import epoch
from tests.test_collect import HourSource

START = datetime(2026, 10, 12, tzinfo=UTC)
SECOND = START + timedelta(hours=1)
THIRD = START + timedelta(hours=2)


def row_for(hour: int) -> tuple:
    return (
        hour,
        "abc123",
        50.0,
        8.6,
        100.0,
        90.0,
        0.0,
        "DLH123  ",
        False,
        False,
        False,
        "1000",
        1000.0,
        1100.0,
        float(hour),
        float(hour),
        hour,
    )


class RangeSource(HourSource):
    def __init__(self, *, fail_hour: int | None = None) -> None:
        super().__init__([])
        self.fail_hour = fail_hour

    def handle(self, sql: str):
        self.queries.append(sql)
        if sql.startswith("DESCRIBE"):
            return [("Column",)], [(name, typ, "", "") for name, typ in self.columns]
        if sql.startswith("SELECT 1 FROM"):
            return [("_col0",)], ([(1,)] if self.global_exists else [])
        if sql.startswith("SELECT"):
            hour = int(sql.split("hour = ")[1].split()[0])
            if hour == self.fail_hour:
                raise SourceError("QUERY_FAILED")
            return [(name,) for name in STATE_VECTOR_COLUMNS], [row_for(hour)]
        raise AssertionError(sql)


def test_parse_duration():
    assert parse_duration("3h") == timedelta(hours=3)
    assert parse_duration("90m") == timedelta(minutes=90)
    assert parse_duration("30s") == timedelta(seconds=30)
    with pytest.raises(Exception, match="invalid duration"):
        parse_duration("later")


def test_range_commits_then_skips_on_repeat(cfg):
    source = RangeSource()
    first = collect_range(
        source, cfg, START, THIRD, pause_seconds=0, max_duration=timedelta(hours=1)
    )
    assert first == {
        "outcome": "finished",
        "reason": None,
        "committed": 2,
        "skipped": 0,
        "next_hour": None,
        "error_class": None,
    }
    digest = (cfg.paths.data_root / hour_manifest_rel(START)).read_bytes()
    second = collect_range(
        RangeSource(), cfg, START, THIRD, pause_seconds=0, max_duration=timedelta(hours=1)
    )
    assert second["committed"] == 0
    assert second["skipped"] == 2
    assert (cfg.paths.data_root / hour_manifest_rel(START)).read_bytes() == digest


def test_range_stops_on_a_failed_hour_and_leaves_the_rest(cfg):
    summary = collect_range(
        RangeSource(fail_hour=epoch(SECOND)),
        cfg,
        START,
        THIRD + timedelta(hours=1),
        pause_seconds=0,
        max_duration=timedelta(hours=1),
    )
    assert summary["outcome"] == "stopped"
    assert summary["reason"] == "hour_failed"
    assert summary["committed"] == 1
    assert summary["error_class"] == "QUERY_FAILED"
    assert summary["next_hour"] == "2026-10-12T01:00:00Z"
    assert not (cfg.paths.data_root / hour_manifest_rel(THIRD)).exists()


def test_range_stops_at_the_duration_limit_before_the_next_hour(cfg):
    times = iter([0.0, 10.0])
    summary = collect_range(
        RangeSource(),
        cfg,
        START,
        THIRD,
        pause_seconds=0,
        max_duration=timedelta(seconds=10),
        clock=lambda: next(times),
    )
    assert summary["outcome"] == "stopped"
    assert summary["reason"] == "max_duration"
    assert summary["committed"] == 0
    assert summary["next_hour"] == "2026-10-12T00:00:00Z"
    assert not (cfg.paths.data_root / hour_manifest_rel(START)).exists()


def test_cli_run_collects_a_range(cfg, capsys, monkeypatch):
    monkeypatch.setattr(cli, "ensure_free_disk", lambda _cfg: None)
    code = cli.main(
        ["run", "--from", "2026-10-12T00:00:00Z", "--until", "2026-10-12T02:00:00Z"],
        connection_factory=lambda _cfg, interactive: RangeSource(),
    )
    assert code == 0
    output = capsys.readouterr().out
    assert "outcome: committed" in output
    assert "run outcome: finished" in output
    assert "committed: 2" in output


def test_cli_run_auth_required(cfg, capsys, monkeypatch):
    monkeypatch.setattr(cli, "ensure_free_disk", lambda _cfg: None)

    def factory(_cfg, interactive):
        raise AuthRequired("AUTH_REQUIRED: renew the OpenSky session with `login`")

    code = cli.main(
        ["run", "--from", "2026-10-12T00:00:00Z", "--until", "2026-10-12T01:00:00Z"],
        connection_factory=factory,
    )
    assert code == 75
    assert "AUTH_REQUIRED" in capsys.readouterr().err


def test_cli_run_rejects_an_empty_range(cfg, capsys, monkeypatch):
    monkeypatch.setattr(cli, "ensure_free_disk", lambda _cfg: None)
    code = cli.main(
        ["run", "--from", "2026-10-12T01:00:00Z", "--until", "2026-10-12T01:00:00Z"],
        connection_factory=lambda _cfg, interactive: RangeSource(),
    )
    assert code == 1
    assert "until must be after from" in capsys.readouterr().err
