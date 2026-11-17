import hashlib
import json

import pyarrow.parquet as pq
import pytest

from energy_pipeline.annual import prepare_year
from energy_pipeline.audit import build_report, save_report, year_windows
from energy_pipeline.download import Download, DownloadError
from energy_pipeline.normalize import STEP, ZONE, ValidationError
from test_audit import completed_runs
from test_normalize import encode, sample_rows


class FakeClient:
    def __init__(self, cache, fail_month=None):
        self.cache = cache
        self.calls = []
        self.fail_month = fail_month

    def download(self, window):
        start = window.start.astimezone(ZONE).date().isoformat()
        until = window.end.astimezone(ZONE).date().isoformat()
        self.calls.append(start)
        if start == self.fail_month:
            raise DownloadError("HTTP 429: cooldown recorded; no automatic retry")
        directory = self.cache / start
        cached = directory.exists()
        if not cached:
            directory.mkdir(parents=True)
            raw = encode(sample_rows(start, until))
            (directory / "source.csv").write_bytes(raw)
            (directory / "download.json").write_text(
                json.dumps(
                    {
                        "input_sha256": hashlib.sha256(raw).hexdigest(),
                        "window_start": window.start.isoformat(),
                        "window_end": window.end.isoformat(),
                        "retrieved_at": "2026-11-17T00:00:00+00:00",
                        "endpoint": "synthetic-test",
                    }
                )
            )
        return Download(directory / "source.csv", directory / "download.json", cached)


def test_prepare_complete_year_exports_verified_snapshot(tmp_path, monkeypatch):
    client = FakeClient(tmp_path / "cache")
    monkeypatch.setattr("energy_pipeline.annual.Client", lambda _: client)
    output = tmp_path / "annual"
    assert prepare_year(2025, client.cache, output) == 0
    assert len(client.calls) == 24
    assert len(list((output / "runs").iterdir())) == 24
    path = next((output / "reports").glob("*/report.json"))
    report = json.loads(path.read_text())
    assert report["status"] == report["annual"]["status"] == "passed"
    assert report["annual"]["actual_rows"] == 35040
    assert report["annual"]["cross_month_boundaries_valid"] == 11
    dataset = path.parent / report["dataset"]["file"]
    assert hashlib.sha256(dataset.read_bytes()).hexdigest() == report["dataset"]["sha256"]
    rows = pq.read_table(dataset).to_pylist()
    assert len(rows) == 35040
    assert all(
        b["interval_start"] - a["interval_start"] == STEP
        for a, b in zip(rows[:-1], rows[1:], strict=True)
    )
    # Mutation after audit cannot be published as a new successful snapshot.
    audited = build_report(output / "runs", year=2025)
    first = output / "runs" / audited["runs"][0]["run_id"] / "observations.parquet"
    first.write_bytes(first.read_bytes() + b"changed")
    with pytest.raises(ValidationError, match="changed after audit"):
        save_report(audited, tmp_path / "rejected")
    assert not list((tmp_path / "rejected").glob("*/observations-2025.parquet"))


def test_missing_months_fail_and_do_not_export_snapshot(tmp_path):
    root = completed_runs(tmp_path, "2025-01-01", "2025-02-01")
    report = build_report(root, year=2025)
    assert report["status"] == "failed"
    assert report["annual"]["actual_months"] == 1
    assert report["annual"]["expected_rows"] == 35040
    saved = save_report(report, tmp_path / "reports")
    assert (saved / "report.json").exists()
    assert not (saved / "observations-2025.parquet").exists()


def test_provider_refusal_stops_before_next_month(tmp_path, monkeypatch):
    client = FakeClient(tmp_path / "cache", fail_month="2025-02-01")
    monkeypatch.setattr("energy_pipeline.annual.Client", lambda _: client)
    with pytest.raises(DownloadError, match="429"):
        prepare_year(2025, client.cache, tmp_path / "annual")
    assert client.calls == ["2025-01-01", "2025-01-01", "2025-02-01"]
    assert not (tmp_path / "annual" / "reports").exists()


def test_invalid_source_stops_before_replay_or_next_month(tmp_path, monkeypatch):
    client = FakeClient(tmp_path / "cache")
    window = year_windows(2025)[0]
    source = client.download(window)
    rows = sample_rows("2025-01-01", "2025-02-01")[:-1]
    raw = encode(rows)
    source.csv_path.write_bytes(raw)
    manifest = json.loads(source.manifest_path.read_text())
    manifest["input_sha256"] = hashlib.sha256(raw).hexdigest()
    source.manifest_path.write_text(json.dumps(manifest))
    client.calls.clear()
    monkeypatch.setattr("energy_pipeline.annual.Client", lambda _: client)
    assert prepare_year(2025, client.cache, tmp_path / "annual") == 1
    assert client.calls == ["2025-01-01"]


def test_future_year_fails_before_constructing_client(tmp_path, monkeypatch):
    def unexpected(_):
        raise AssertionError("client must not be created")

    monkeypatch.setattr("energy_pipeline.annual.Client", unexpected)
    with pytest.raises(ValidationError, match="fully completed"):
        prepare_year(2099, tmp_path / "cache", tmp_path / "annual")


def test_leap_year_expected_count_and_dst_months():
    leap = year_windows(2024)
    assert sum(window.expected_rows for window in leap) == 35136
    normal = year_windows(2025)
    assert sum(window.expected_rows for window in normal) == 35040
    assert normal[2].expected_rows == 31 * 96 - 4
    assert normal[9].expected_rows == 31 * 96 + 4
