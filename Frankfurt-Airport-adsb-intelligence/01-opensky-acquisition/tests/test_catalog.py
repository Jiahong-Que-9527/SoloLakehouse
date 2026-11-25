from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from opensky_ingest.batch import Batch, validate_batch
from opensky_ingest.catalog import (
    BATCH_MANIFEST_PARQUET,
    CONTRACT_NAME,
    FLIGHT_MANIFEST_PARQUET,
    HOUR_MANIFEST_PARQUET,
    build_catalog,
    dataset_contract,
    dataset_summary,
    export_manifests,
)
from opensky_ingest.errors import IngestError
from opensky_ingest.fetch import collect_hour
from opensky_ingest.flights import collect_flight_day
from opensky_ingest.manifest import hour_parquet_rel
from opensky_ingest.publish import accept_batch, publish_batch
from opensky_ingest.util import day_epoch, epoch
from opensky_ingest.verify import restore_check, verify_dataset
from tests.test_batch import _batch
from tests.test_collect import HourSource, sample_row
from tests.test_flights import FlightSource, sample_flight

DAY = date(2026, 10, 15)


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


def _one_batch() -> dict[str, Batch]:
    return {"t01": _batch()}


def test_contract_records_bounds_sql_and_gaps(cfg):
    contract = dataset_contract(cfg)
    assert contract["dataset_id"] == "eddf_r75km"
    assert contract["period"]["hours"] == 43_824
    assert contract["bbox"]["south"] == 49.36
    assert "{hour_epoch}" in contract["sql_templates"]["state_vectors"]
    assert "estdepartureairport" in contract["sql_templates"]["flights"]
    assert contract["serials"]["included"] is False
    assert any(gap["start"].startswith("2023-01-18") for gap in contract["known_gaps"])
    assert {epoch["id"] for epoch in contract["processing_epochs"]} == {"A", "B", "C"}


def test_export_writes_tables_and_contract(cfg):
    _fill(cfg)
    record = export_manifests(cfg)
    assert record["hours"] == 24
    assert record["flight_days"] == 1
    out = cfg.paths.data_root / "metadata" / "datasets"
    assert (out / HOUR_MANIFEST_PARQUET).exists()
    assert (out / FLIGHT_MANIFEST_PARQUET).exists()
    assert (out / BATCH_MANIFEST_PARQUET).exists()
    assert (out / CONTRACT_NAME).exists()
    import pyarrow.parquet as pq

    hours = pq.read_table(out / HOUR_MANIFEST_PARQUET).to_pylist()
    assert all(row["batch_id"] == "b01" for row in hours)
    complete = [row for row in hours if row["status"] == "complete"]
    assert len(complete) == 24
    assert all(row["path"] and row["path"].endswith(".parquet") for row in complete)
    flights = pq.read_table(out / FLIGHT_MANIFEST_PARQUET).to_pylist()
    assert flights[0]["dataset_id"] == "eddf_flights"
    assert flights[0]["status"] == "complete"


def test_verify_passes_on_a_collected_day_and_detects_tampering(cfg):
    _fill(cfg)
    validate_batch(cfg, _batch())
    record = verify_dataset(cfg, batches=_one_batch(), progress=print, every=10)
    assert record["outcome"] == "passed", record["problems"]
    assert record["files_hashed"] == 25
    assert record["totals"]["rows"] > 0

    # A corrupted file is detected through the manifest checksum.
    hour = datetime(DAY.year, DAY.month, DAY.day, 5, tzinfo=UTC)
    path = cfg.paths.data_root / hour_parquet_rel("eddf_r75km", "v1", hour)
    body = bytearray(path.read_bytes())
    body[len(body) // 2] ^= 0xFF  # same size, different content
    path.write_bytes(bytes(body))
    record = verify_dataset(cfg, batches=_one_batch())
    assert record["outcome"] == "failed"
    assert any(problem["problem"] == "checksum" for problem in record["problems"])

    # A missing file is detected as well.
    path.unlink()
    record = verify_dataset(cfg, batches=_one_batch())
    assert any(problem["problem"] == "file_missing" for problem in record["problems"])


def test_verify_reports_missing_manifests_and_orphans(cfg):
    record = verify_dataset(cfg, batches=_one_batch())
    assert record["outcome"] == "failed"
    assert record["counts"]["hours"].get("missing") == 24

    _fill(cfg)
    validate_batch(cfg, _batch())
    orphan = cfg.paths.data_root / "bronze" / "opensky" / "state_vectors" / "eddf_r75km" / "v1"
    stray = orphan / "dt=2026-10-14" / "hour-99.parquet"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_bytes(b"parquet")
    record = verify_dataset(cfg, batches=_one_batch())
    assert any(problem["problem"] == "orphan" for problem in record["problems"])


def test_restore_check_requires_a_published_batch(cfg):
    with pytest.raises(IngestError):
        restore_check(cfg, _batch())


def test_restore_check_recovers_the_batch_from_the_backup(cfg):
    _fill(cfg)
    validate_batch(cfg, _batch())
    accept_batch(cfg, _batch(), notes="restore test")
    publish_batch(cfg, _batch())
    record = restore_check(cfg, _batch())
    assert record["outcome"] == "passed", record["mismatches"]
    assert record["checked"] == 25
    assert record["bytes"] > 0
    assert record["restored_to"] is None
    assert not (cfg.paths.data_root / "staging" / "restore-t01").exists()

    record = restore_check(cfg, _batch(), keep=True)
    assert record["restored_to"] is not None
    assert (cfg.paths.data_root / "staging" / "restore-t01").exists()


def test_restore_check_skips_committed_hours_without_files(cfg):
    _fill(cfg)
    validate_batch(cfg, _batch())
    accept_batch(cfg, _batch(), notes="restore test")
    publish_batch(cfg, _batch())
    # A source_gap hour is committed without a file; restore must skip it.
    hour = datetime(DAY.year, DAY.month, DAY.day, 7, tzinfo=UTC)
    from opensky_ingest.manifest import hour_manifest_rel, hour_parquet_rel, write_manifest

    parquet = cfg.paths.data_root / hour_parquet_rel("eddf_r75km", "v1", hour)
    parquet.unlink()
    write_manifest(
        cfg.paths.data_root / hour_manifest_rel(hour),
        {"hour": epoch(hour), "status": "source_gap", "collected_at": "2026-01-01T00:00:00Z"},
    )
    (cfg.paths.backup_root / hour_parquet_rel("eddf_r75km", "v1", hour)).unlink()
    record = restore_check(cfg, _batch())
    assert record["outcome"] == "passed", record["mismatches"]
    assert record["checked"] == 25


def test_restore_check_detects_a_tampered_backup(cfg):
    _fill(cfg)
    validate_batch(cfg, _batch())
    accept_batch(cfg, _batch(), notes="restore test")
    publish_batch(cfg, _batch())
    hour = datetime(DAY.year, DAY.month, DAY.day, 6, tzinfo=UTC)
    backup_file = cfg.paths.backup_root / hour_parquet_rel("eddf_r75km", "v1", hour)
    backup_file.write_bytes(b"not parquet")
    record = restore_check(cfg, _batch())
    assert record["outcome"] == "failed"
    assert any(": checksum" in item for item in record["mismatches"])


def test_catalog_and_summary_need_the_export_first(cfg):
    pytest.importorskip("duckdb")
    from opensky_ingest.config import ConfigError

    with pytest.raises(ConfigError):
        build_catalog(cfg)


def test_catalog_views_read_through_manifests(cfg):
    pytest.importorskip("duckdb")
    _fill(cfg)
    validate_batch(cfg, _batch())
    export_manifests(cfg)
    record = build_catalog(cfg)
    assert record["hour_files"] == 24
    assert record["flight_files"] == 1

    import duckdb

    con = duckdb.connect(str(cfg.paths.data_root / "metadata" / "datasets" / "catalog.duckdb"))
    try:
        rows = con.execute("SELECT count(*) FROM state_vectors").fetchone()[0]
        assert (
            rows
            == con.execute(
                "SELECT sum(rows) FROM hour_manifest WHERE status = 'complete'"
            ).fetchone()[0]
        )
        assert con.execute("SELECT count(*) FROM flights").fetchone()[0] == 1
        assert con.execute("SELECT count(*) FROM known_gaps").fetchone()[0] == 21
        assert con.execute("SELECT count(*) FROM processing_epochs").fetchone()[0] == 3
        gaps = con.execute(
            "SELECT count(*) FROM hour_manifest WHERE status = 'source_gap'"
        ).fetchone()[0]
        assert gaps == 0
    finally:
        con.close()


def test_summary_counts_the_datasets(cfg):
    pytest.importorskip("duckdb")
    _fill(cfg)
    validate_batch(cfg, _batch())
    export_manifests(cfg)
    record = dataset_summary(cfg)
    assert record["state_vectors"]["complete"] == 24
    assert record["state_vectors"]["unique_aircraft"] == 1  # all rows share icao24 abc123
    assert record["flights"]["complete"] == 1
    assert record["flights"]["rows"] == 1
    assert record["per_month"][0]["month"] == "2026-10"
    assert record["known_gaps"]["count"] == 21
    summary = cfg.paths.data_root / "metadata" / "datasets" / "dataset_summary.json"
    assert summary.exists()
