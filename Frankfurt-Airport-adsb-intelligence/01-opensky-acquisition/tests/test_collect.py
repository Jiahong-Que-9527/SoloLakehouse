from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pyarrow.parquet as pq
import pytest

from opensky_ingest import cli
from opensky_ingest.fetch import InjectedCrash, collect_hour
from opensky_ingest.manifest import hour_manifest_rel, hour_parquet_rel
from opensky_ingest.query import state_vector_sql
from opensky_ingest.schema import STATE_VECTOR_COLUMNS, TRINO_TYPES
from opensky_ingest.util import epoch

HOUR = datetime(2026, 10, 15, 12, tzinfo=UTC)
GAP_HOUR = datetime(2026, 1, 3, 12, tzinfo=UTC)


def sample_row(
    icao: str = "abc123",
    time: int | None = None,
    lat: float = 50.0,
    lon: float = 8.6,
    onground: bool = False,
    lastcontact: float | None = None,
    callsign: str = "DLH123  ",
) -> tuple:
    stamp = epoch(HOUR) if time is None else time
    contact = float(stamp) if lastcontact is None else lastcontact
    return (
        stamp,
        icao,
        lat,
        lon,
        100.0,
        90.0,
        0.0,
        callsign,
        onground,
        False,
        False,
        "1000",
        1000.0,
        1100.0,
        float(stamp),
        contact,
        epoch(HOUR),
    )


class HourCursor:
    def __init__(self, connection: HourSource) -> None:
        self._connection = connection
        self.description: list[tuple] | None = None
        self.stats = connection.stats
        self.query_id = connection.query_id
        self._rows: list[tuple] = []

    def execute(self, sql: str) -> None:
        self.description, self._rows = self._connection.handle(sql)

    def __iter__(self):
        return iter(self._rows)

    def cancel(self) -> None:
        self._connection.cancelled = True

    def close(self) -> None:
        pass


class HourSource:
    def __init__(
        self,
        rows: list[tuple],
        *,
        global_exists: bool = True,
        columns: list[tuple[str, str]] | None = None,
    ) -> None:
        self.rows = rows
        self.global_exists = global_exists
        self.columns = columns or [*TRINO_TYPES.items(), ("serials", "array(integer)")]
        self.queries: list[str] = []
        self.stats: dict[str, Any] = {"processedBytes": 1_000}
        self.query_id = "q-hour"
        self.cancelled = False

    def cursor(self) -> HourCursor:
        return HourCursor(self)

    def close(self) -> None:
        pass

    def handle(self, sql: str):
        self.queries.append(sql)
        if sql.startswith("DESCRIBE"):
            return [("Column",)], [(name, typ, "", "") for name, typ in self.columns]
        if sql.startswith("SELECT 1 FROM"):
            return [("_col0",)], ([(1,)] if self.global_exists else [])
        if sql.startswith("SELECT"):
            return [(name,) for name in STATE_VECTOR_COLUMNS], list(self.rows)
        raise AssertionError(sql)


def manifest_path(cfg, hour: datetime):
    return cfg.paths.data_root / hour_manifest_rel(hour)


def parquet_path(cfg, hour: datetime):
    return cfg.paths.data_root / hour_parquet_rel(cfg.region.id, cfg.region.version, hour)


def test_sql_excludes_serials_and_filters_the_hour(cfg):
    sql = state_vector_sql(cfg, HOUR)
    assert "serials" not in sql
    assert f"hour = {epoch(HOUR)}" in sql
    assert "ORDER BY" not in sql
    assert "LIMIT" not in sql


def test_commit_and_repeat_does_not_change_the_manifest(cfg):
    source = HourSource([sample_row()])
    first = collect_hour(source, cfg, HOUR, run_id="r1", pause_seconds=0)
    text = manifest_path(cfg, HOUR).read_text()
    body = json.loads(text)
    assert first["outcome"] == "committed"
    assert body["status"] == "complete"
    assert body["rows"] == 1
    assert body["include_serials"] is False
    assert "outcome" not in body
    queries_after_commit = len(source.queries)
    second = collect_hour(source, cfg, HOUR, run_id="r2", pause_seconds=0)
    assert second["outcome"] == "skipped"
    assert manifest_path(cfg, HOUR).read_text() == text
    assert len(source.queries) == queries_after_commit
    table = pq.read_table(parquet_path(cfg, HOUR))
    assert table.column("callsign")[0].as_py() == "DLH123  "
    assert pq.read_metadata(parquet_path(cfg, HOUR)).row_group(0).column(0).compression == "ZSTD"


def test_duplicates_are_kept_and_counted(cfg):
    collect_hour(source := HourSource([sample_row(), sample_row()]), cfg, HOUR, pause_seconds=0)
    body = json.loads(manifest_path(cfg, HOUR).read_text())
    assert body["rows"] == 2
    assert body["duplicate_key_rows"] == 1
    assert not source.cancelled


def test_stale_rows_are_counted(cfg):
    stale = sample_row(lastcontact=float(epoch(HOUR) - 30))
    collect_hour(HourSource([stale]), cfg, HOUR, pause_seconds=0)
    body = json.loads(manifest_path(cfg, HOUR).read_text())
    assert body["stale_or_unknown_rows"] == 1


def test_row_outside_the_box_is_not_committed(cfg):
    result = collect_hour(HourSource([sample_row(lat=1.0)]), cfg, HOUR, pause_seconds=0)
    assert result["outcome"] == "failed"
    assert result["error_class"] == "VALIDATION"
    assert not parquet_path(cfg, HOUR).exists()
    assert not manifest_path(cfg, HOUR).exists()


def test_empty_hour_when_the_global_partition_has_rows(cfg):
    result = collect_hour(HourSource([], global_exists=True), cfg, HOUR, pause_seconds=0)
    assert result["status"] == "empty"
    assert not parquet_path(cfg, HOUR).exists()
    assert json.loads(manifest_path(cfg, HOUR).read_text())["path"] is None


def test_source_gap_when_the_hour_is_inside_a_documented_gap(cfg):
    result = collect_hour(HourSource([], global_exists=False), cfg, GAP_HOUR, pause_seconds=0)
    assert result["status"] == "source_gap"
    assert not parquet_path(cfg, GAP_HOUR).exists()


def test_missing_source_hour_is_failed_not_committed(cfg):
    result = collect_hour(HourSource([], global_exists=False), cfg, HOUR, pause_seconds=0)
    assert result["outcome"] == "failed"
    assert result["error_class"] == "SOURCE_MISSING"
    assert not manifest_path(cfg, HOUR).exists()


def test_rows_inside_a_known_gap_are_flagged(cfg):
    row = sample_row(time=epoch(GAP_HOUR))
    row = row[:-1] + (epoch(GAP_HOUR),)
    result = collect_hour(HourSource([row]), cfg, GAP_HOUR, pause_seconds=0)
    assert result["status"] == "complete"
    assert "known_gap_overlap" in result["flags"]


def test_crash_after_publish_is_redone_without_leaving_the_orphan(cfg):
    source = HourSource([sample_row()])
    with pytest.raises(InjectedCrash):
        collect_hour(source, cfg, HOUR, run_id="r1", crash_after="published", pause_seconds=0)
    assert parquet_path(cfg, HOUR).exists()
    assert not manifest_path(cfg, HOUR).exists()
    result = collect_hour(source, cfg, HOUR, run_id="r2", pause_seconds=0)
    assert result["outcome"] == "committed"
    quarantined = list((cfg.paths.data_root / "quarantine").rglob("*.parquet"))
    assert quarantined
    assert parquet_path(cfg, HOUR).exists()


def test_crash_after_manifest_is_already_committed(cfg):
    source = HourSource([sample_row()])
    with pytest.raises(InjectedCrash):
        collect_hour(source, cfg, HOUR, run_id="r1", crash_after="manifest", pause_seconds=0)
    queries = len(source.queries)
    result = collect_hour(source, cfg, HOUR, run_id="r2", pause_seconds=0)
    assert result["outcome"] == "skipped"
    assert len(source.queries) == queries


def test_checksum_mismatch_does_not_overwrite_the_file_in_place(cfg):
    collect_hour(HourSource([sample_row()]), cfg, HOUR, pause_seconds=0)
    path = parquet_path(cfg, HOUR)
    original = path.read_bytes()
    path.write_bytes(original + b"x")
    result = collect_hour(
        HourSource([sample_row(icao="other")]), cfg, HOUR, run_id="r2", pause_seconds=0
    )
    assert result["outcome"] == "failed"
    assert result["error_class"] == "CHECKSUM_MISMATCH"
    assert not path.exists()
    quarantined = list((cfg.paths.data_root / "quarantine").rglob("*.parquet"))
    assert any(item.read_bytes() == original + b"x" for item in quarantined)


def test_row_cap_stops_without_a_commit(cfg):
    result = collect_hour(
        HourSource([sample_row(), sample_row(icao="def456")]),
        cfg,
        HOUR,
        row_cap=1,
        pause_seconds=0,
    )
    assert result["error_class"] == "ROW_CAP_EXCEEDED"
    assert not manifest_path(cfg, HOUR).exists()


def test_schema_drift_stops_the_run(cfg):
    columns = [(name, typ) for name, typ in TRINO_TYPES.items() if name != "squawk"]
    with pytest.raises(Exception, match="SCHEMA_DRIFT"):
        collect_hour(HourSource([sample_row()], columns=columns), cfg, HOUR, pause_seconds=0)
    assert not manifest_path(cfg, HOUR).exists()


def test_cli_collect_hour(cfg, capsys, monkeypatch):
    monkeypatch.setattr(cli, "ensure_free_disk", lambda _cfg: None)
    code = cli.main(
        ["collect-hour", "--hour", "2026-10-15T12:00:00Z"],
        connection_factory=lambda _cfg, interactive: HourSource([sample_row()]),
    )
    assert code == 0
    assert "outcome: committed" in capsys.readouterr().out
