from __future__ import annotations

import json
from datetime import timedelta

from opensky_ingest import cli
from opensky_ingest.crosscheck import cross_check_hours
from opensky_ingest.fetch import collect_hour
from opensky_ingest.util import epoch
from tests.test_collect import HOUR, HourSource, sample_row


def _receipt(rows: int, ground: int = 1) -> dict:
    stamp = epoch(HOUR)
    return {
        "rows": rows,
        "aircraft": 1,
        "min_time": stamp,
        "max_time": stamp,
        "ground_rows": ground,
    }


def _hour(cfg, receipts):
    collect_hour(
        HourSource(
            [
                sample_row(onground=True),
                sample_row(icao="def456", lat=50.5, time=epoch(HOUR) + 30),
            ]
        ),
        cfg,
        HOUR,
        pause_seconds=0,
    )
    path = receipts / f"{epoch(HOUR)}.receipt.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(_receipt(1)))


def test_cross_check_counts_only_the_legacy_box(cfg, tmp_path):
    receipts = tmp_path / "receipts"
    _hour(cfg, receipts)
    result = cross_check_hours(cfg, HOUR, HOUR + timedelta(hours=1), receipts)
    assert result["outcome"] == "matched"
    assert result["hours"][0]["file"] == _receipt(1)
    assert (cfg.paths.data_root / "reports" / "cross-check" / f"{result['run_id']}.json").exists()


def test_cross_check_reports_a_row_difference(cfg, tmp_path):
    receipts = tmp_path / "receipts"
    _hour(cfg, receipts)
    path = receipts / f"{epoch(HOUR)}.receipt.json"
    path.write_text(json.dumps(_receipt(9)))
    result = cross_check_hours(cfg, HOUR, HOUR + timedelta(hours=1), receipts)
    assert result["outcome"] == "mismatched"
    assert result["hours"][0]["mismatches"] == ["rows"]


def test_cli_cross_check(cfg, tmp_path, capsys):
    receipts = tmp_path / "receipts"
    _hour(cfg, receipts)
    code = cli.main(
        [
            "cross-check",
            "--from",
            "2026-10-15T12:00:00Z",
            "--until",
            "2026-10-15T13:00:00Z",
            "--receipts",
            str(receipts),
        ]
    )
    assert code == 0
    assert "cross-check outcome: matched" in capsys.readouterr().out
