from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from opensky_ingest import cli
from opensky_ingest.batch import Batch, _anomalies, load_batches, validate_batch
from opensky_ingest.errors import IngestError
from opensky_ingest.fetch import collect_hour
from opensky_ingest.flights import collect_flight_day
from opensky_ingest.manifest import hour_parquet_rel
from opensky_ingest.publish import accept_batch, publish_batch
from opensky_ingest.report import write_report
from opensky_ingest.util import day_epoch, epoch, write_json_atomic
from tests.test_collect import HourSource, sample_row
from tests.test_flights import FlightSource, sample_flight

DAY = date(2026, 10, 15)


def _batch() -> Batch:
    return Batch("t01", "2026-10", DAY, DAY + timedelta(days=1), DAY, DAY + timedelta(days=1))


def _row(hour: datetime) -> tuple:
    stamp = epoch(hour)
    values = list(sample_row(time=stamp))
    values[-1] = stamp
    return tuple(values)


def _fill(cfg) -> None:
    start = datetime(DAY.year, DAY.month, DAY.day, tzinfo=UTC)
    for offset in range(24):
        hour = start + timedelta(hours=offset)
        collect_hour(HourSource([_row(hour)]), cfg, hour, pause_seconds=0)
    stamp = day_epoch(DAY)
    collect_flight_day(
        FlightSource([sample_flight(firstseen=stamp + 100, day=stamp)]),
        cfg,
        DAY,
        pause_seconds=0,
    )


def test_batches_cover_the_dataset_period():
    found = load_batches()
    assert len(found) == 60
    assert sum(len(list(batch.hours())) for batch in found.values()) == 43_824
    flights = {day for batch in found.values() for day in batch.flight_days()}
    assert len(flights) == 1_827
    assert date(2026, 11, 1) in set(found["b01"].flight_days())
    assert date(2026, 11, 1) not in set(found["b01"].hours())


def test_validate_fails_when_the_batch_is_missing(cfg):
    result = validate_batch(cfg, _batch())
    assert result["outcome"] == "failed"
    assert result["expected_hours"] == 24
    assert any(item["problem"] == "missing_manifest" for item in result["problems"])


def test_validate_accept_and_publish_a_complete_day(cfg):
    _fill(cfg)
    result = validate_batch(cfg, _batch())
    assert result["outcome"] == "passed"
    assert result["complete"] == 24
    assert result["flights_complete"] == 1
    assert result["rehashed"] == 25
    report = write_report(cfg, _batch())
    assert report["outcome"] == "passed"
    accepted = accept_batch(cfg, _batch(), notes="pilot day")
    assert accepted["outcome"] == "accepted"
    published = publish_batch(cfg, _batch())
    assert published["outcome"] == "published"
    assert published["checked"] == 25
    copied = cfg.paths.backup_root / hour_parquet_rel(
        "eddf_r75km", "v1", datetime(2026, 10, 15, tzinfo=UTC)
    )
    assert copied.exists()


def test_checksum_mismatch_fails_validation(cfg):
    _fill(cfg)
    path = cfg.paths.data_root / hour_parquet_rel(
        "eddf_r75km", "v1", datetime(2026, 10, 15, 3, tzinfo=UTC)
    )
    path.write_bytes(path.read_bytes() + b"x")
    result = validate_batch(cfg, _batch())
    assert result["outcome"] == "failed"
    assert {"hour": "2026-10-15T03:00:00Z", "problem": "checksum"} in result["problems"]


def test_an_extra_file_is_an_orphan(cfg):
    _fill(cfg)
    extra = cfg.paths.data_root / hour_parquet_rel(
        "eddf_r75km", "v1", datetime(2026, 10, 15, tzinfo=UTC)
    )
    extra.with_name("hour-extra.parquet").write_bytes(b"not parquet")
    result = validate_batch(cfg, _batch())
    assert any(item["problem"] == "orphan" for item in result["problems"])


def test_accept_refuses_a_failed_batch_and_unexplained_anomalies(cfg):
    validate_batch(cfg, _batch())
    with pytest.raises(IngestError, match="BATCH_NOT_VALIDATED"):
        accept_batch(cfg, _batch())
    path = cfg.paths.data_root / "metadata" / "manifests" / "batches" / "t01.json"
    write_json_atomic(
        path,
        {
            "anomalies": [{"hour": "2026-10-15T00:00:00Z", "rows": 1, "median_rows": 1000}],
            "batch_id": "t01",
            "days": [],
            "outcome": "review",
        },
    )
    with pytest.raises(IngestError, match="ANOMALIES_NEED_NOTES"):
        accept_batch(cfg, _batch())
    assert accept_batch(cfg, _batch(), notes="quiet night")["outcome"] == "accepted"


def test_publish_refuses_a_batch_that_is_not_accepted(cfg):
    _fill(cfg)
    validate_batch(cfg, _batch())
    with pytest.raises(IngestError, match="BATCH_NOT_ACCEPTED"):
        publish_batch(cfg, _batch())


def test_anomaly_rule_flags_an_hour_far_below_its_peers():
    counts = []
    for day in (5, 12, 19):
        counts.append({"key": f"2026-10-{day:02d}T03:00:00Z", "rows": 4000, "status": "complete"})
    counts[-1]["rows"] = 10
    found = _anomalies(counts)
    assert [item["hour"] for item in found] == ["2026-10-19T03:00:00Z"]


def test_cli_validate_reports_a_missing_batch(cfg, capsys):
    code = cli.main(["validate", "--batch", "b24"])
    assert code == 1
    assert "validate outcome: failed" in capsys.readouterr().out
