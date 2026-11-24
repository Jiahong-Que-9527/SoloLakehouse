"""Check the release gate, label-only projection, and immutable Delta replay."""

import json
import tempfile
import unittest
from datetime import date
from importlib.util import find_spec
from pathlib import Path
from unittest.mock import Mock

import pyarrow as pa
import pyarrow.parquet as pq

from lakehouse import GOLD_FIELDS, LocalDelta, publish
from release_inputs import INPUT_SCHEMA, file_digest, load_release


def build_release(root: Path, month: str = "2024-11") -> Path:
    release_id = f"geometry-v2-{month}"
    folder = root / release_id
    (folder / "data").mkdir(parents=True)
    event = {"day_utc": date.fromisoformat(month + "-01"), "flight_key": "abcdef:1000", "icao24": "abcdef",
             "lastseen_epoch_s": 1000, "touchdown_estimate_epoch_s": 990, "surface_start_epoch_s": 1001,
             "taxi_end_epoch_s": 1031, "taxi_in_s": 30, "surface_point_count": 2, "status": "labeled"}
    pq.write_table(pa.Table.from_pylist([event], schema=INPUT_SCHEMA), folder / "data/part-0001.parquet")
    (folder / "contract.yaml").write_text("version: '2'\n")
    manifest = {"release_id": release_id, "data_product": "ground-ops", "contract_version": "2",
                "release_schema_version": "release-v1", "schema_version": "gold-ground-ops-v1",
                "label_version": "taxi-in-geometry-v2", "grain": ["day_utc", "flight_key"],
                "created_at": "2026-11-22T20:10:20+00:00", "files": {name: {"sha256": file_digest(folder / name)}
                for name in ("contract.yaml", "data/part-0001.parquet")}}
    manifest["files"]["data/part-0001.parquet"]["rows"] = 1
    controls = {"manifest.json": manifest, "validation.json": {"status": "passed"},
                "approval.json": {"approver": "fixture", "contract_version": "2"}, "_SUCCESS": {}}
    for name, data in controls.items():
        (folder / name).write_text(json.dumps({"release_id": release_id, **data}))
    return folder


@unittest.skipUnless(find_spec("deltalake"), "historical Delta tests require the legacy dependency group")
class LakehouseTests(unittest.TestCase):
    def test_replay_keeps_versions_and_gold_contains_only_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = build_release(root)
            target = LocalDelta(root / "delta")
            first = publish(source, target)
            second = publish(source, target)
            self.assertEqual(list(first["tables"]), list(second["tables"]))
            for name, result in first["tables"].items():
                replay = second["tables"][name]
                self.assertFalse(result["reused"])
                self.assertTrue(replay["reused"])
                self.assertEqual(replay["sha256"], result["sha256"])
                self.assertEqual(replay["version"], result["version"])
            gold = target.read("aviation_gold_taxi_in_labels", first["release_id"])
            self.assertEqual(gold.column_names, GOLD_FIELDS)
            self.assertEqual(gold["taxi_in_s"].to_pylist(), [30])

    def test_tampered_contract_stops_before_delta_access(self):
        with tempfile.TemporaryDirectory() as directory:
            source = build_release(Path(directory))
            (source / "contract.yaml").write_text("version: invalid\n")
            target = Mock()
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                publish(source, target)
            self.assertEqual(target.mock_calls, [])

    def test_recovery_validates_the_existing_slice_before_advancing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = LocalDelta(root / "delta")
            source = build_release(root)
            _, bronze = load_release(source)
            target.append("aviation_bronze_release", bronze)
            report = publish(source, target)
            self.assertTrue(report["tables"]["aviation_bronze_release"]["reused"])
            self.assertFalse(report["tables"]["aviation_silver_arrivals"]["reused"])
