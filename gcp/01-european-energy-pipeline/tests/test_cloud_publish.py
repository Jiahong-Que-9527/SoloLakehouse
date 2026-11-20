"""Cloud publish behaviour: quality gate, idempotent republish, raw immutability."""

import hashlib
import json
from datetime import datetime

from energy_pipeline.cloud_publish import publish_window
from energy_pipeline.normalize import Window
from test_normalize import encode, sample_rows

WEEK = Window.from_dates("2026-06-08", "2026-06-15")
WEEK_CSV = encode(sample_rows("2026-06-08", "2026-06-15"))
PREFIX = "raw/sample/de_load/dt=2026-06-08"


class FakeRawStore:
    """Port double: immutable object storage; overwriting a committed name fails."""

    def __init__(self):
        self.objects = {}

    def put_object(self, bucket, prefix, name, payload):
        path = f"gs://{bucket}/{prefix}/{name}"
        if path in self.objects:
            raise AssertionError(f"committed object overwritten: {path}")
        self.objects[path] = payload
        return path


class FakeWarehouse:
    """Port double: merge on (area, metric, interval_start); releases are appended."""

    def __init__(self):
        self.rows = {}
        self.releases = []

    def merge_observations(self, project, dataset, table, rows, release_id, ingested_at):
        merged = 0
        for row in rows.to_pylist():
            row["release_id"] = release_id
            row["ingested_at"] = ingested_at
            key = (row["area"], row["metric"], row["interval_start"])
            if key not in self.rows:
                merged += 1
            self.rows[key] = row
        return merged

    def insert_release(self, project, dataset, record):
        self.releases.append(record)


def publish(store=None, warehouse=None, raw=WEEK_CSV, window=WEEK, **kwargs):
    return publish_window(
        store or FakeRawStore(),
        warehouse or FakeWarehouse(),
        csv_bytes=raw,
        window=window,
        bucket="test-bucket",
        project="test-project",
        dataset="energy",
        input_name="sample_week.csv",
        **kwargs,
    )


def manifest_of(store):
    payload = next(p for path, p in store.objects.items() if path.endswith(".manifest.json"))
    return json.loads(payload)


def failed(raw, window=WEEK):
    store, warehouse = FakeRawStore(), FakeWarehouse()
    result = publish(store, warehouse, raw=raw, window=window)
    return result, store, warehouse


def test_publish_sample_week_passes():
    store, warehouse = FakeRawStore(), FakeWarehouse()
    result = publish(store, warehouse)
    assert result.quality_status == "passed"
    assert result.row_count == 672
    assert result.input_sha256 == hashlib.sha256(WEEK_CSV).hexdigest()
    raw_objects = [path for path in store.objects if path.endswith(".csv")]
    assert len(raw_objects) == 1 and raw_objects[0].startswith(f"gs://test-bucket/{PREFIX}/")
    manifest = manifest_of(store)
    assert manifest["quality_status"] == "passed"
    assert manifest["row_count"] == 672
    assert manifest["attribution"] == "Bundesnetzagentur | SMARD.de"
    assert manifest["license"] == "CC-BY-4.0"
    assert manifest["source"] == "sample"
    release = warehouse.releases[0]
    assert release["quality_status"] == "passed"
    assert release["row_count"] == 672
    assert release["release_id"] == result.release_id
    assert release["input_checksum"] == result.input_sha256
    assert release["window_start"] == "2026-06-08" and release["window_end"] == "2026-06-15"
    assert len(warehouse.rows) == 672


def test_publish_adds_release_columns_to_merged_rows_only():
    store, warehouse = FakeRawStore(), FakeWarehouse()
    result = publish(store, warehouse)
    row = next(iter(warehouse.rows.values()))
    assert set(row) == {
        "interval_start",
        "interval_end",
        "area",
        "metric",
        "value",
        "unit",
        "source",
        "release_id",
        "ingested_at",
    }
    assert row["release_id"] == result.release_id
    assert isinstance(row["ingested_at"], datetime) and row["ingested_at"].tzinfo is not None


def test_duplicate_key_fails_without_table_change():
    rows = sample_rows("2026-06-08", "2026-06-15")
    rows.insert(18, rows[18])
    result, store, warehouse = failed(encode(rows))
    assert result.quality_status == "failed"
    assert result.row_count == 0
    assert warehouse.rows == {}
    assert warehouse.releases[-1]["quality_status"] == "failed"
    assert any(path.endswith(".csv") for path in store.objects)
    assert manifest_of(store)["quality_status"] == "failed"


def test_missing_interval_fails_without_table_change():
    rows = sample_rows("2026-06-08", "2026-06-15")
    rows.pop(18)
    result, _, warehouse = failed(encode(rows))
    assert result.quality_status == "failed"
    assert warehouse.rows == {}


def test_null_value_fails_without_table_change():
    rows = sample_rows("2026-06-08", "2026-06-15")
    rows[16][2] = ""
    result, _, warehouse = failed(encode(rows))
    assert result.quality_status == "failed"
    assert warehouse.rows == {}


def test_autumn_dst_sample_publishes_100_rows():
    window = Window.from_dates("2026-10-25", "2026-10-26")
    result = publish(
        raw=encode(sample_rows("2026-10-25", "2026-10-26")),
        window=window,
    )
    assert result.quality_status == "passed"
    assert result.row_count == 100


def test_repeat_run_same_keys_new_release_rows():
    store, warehouse = FakeRawStore(), FakeWarehouse()
    first = publish(store, warehouse)
    keys = {key[2] for key in warehouse.rows}
    second = publish(store, warehouse)
    assert first.run_id != second.run_id
    assert first.release_id != second.release_id
    assert {r["interval_start"] for r in warehouse.rows.values()} == keys
    assert len(warehouse.rows) == 672
    assert len(warehouse.releases) == 2
    assert all(release["quality_status"] == "passed" for release in warehouse.releases)


def test_no_overwrite_of_committed_objects():
    store = FakeRawStore()
    publish(store)
    publish(store)
    assert len(store.objects) == 4  # 2 runs x (csv + manifest), all distinct names
