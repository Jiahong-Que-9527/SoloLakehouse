"""Regression coverage for the sequential Geometry v2 import checkpoint."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import geometry_series


class GeometrySeriesTests(unittest.TestCase):
    def test_partial_failure_resumes_at_failed_month(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            args = SimpleNamespace(evidence_dir=base, release_dir=base, project="test",
                                   landing_bucket="landing", gold_bucket="gold", uploader="upload",
                                   max_bytes_billed=104857600, replay=False)
            counts = {"rows": 2, "labeled_rows": 1, "duplicate_keys": 0}
            first, second = [f"geometry-v2-{m}" for m in geometry_series.release_months("2024-12", "2025-01")]
            releases = {rid: {"counts": counts, "manifest_sha256": rid} for rid in (first, second)}
            first_result = {"status": "ingested", "release_id": first, "geometry_counts": counts}
            with patch.object(geometry_series, "command", side_effect=[{}, first_result, RuntimeError("stopped")]):
                with self.assertRaisesRegex(RuntimeError, "stopped"):
                    geometry_series.import_series(args, releases)
            self.assertTrue((base / f"{first}.json").exists())
            self.assertFalse((base / f"{second}.json").exists())

            second_result = {"status": "ingested", "release_id": second, "geometry_counts": counts}
            with patch.object(geometry_series, "command", side_effect=[{}, second_result]) as run:
                geometry_series.import_series(args, releases)
            self.assertEqual(run.call_count, 2)
            self.assertEqual(run.call_args_list[0].args[1], str(base / second))
            result = json.loads((base / f"{second}.json").read_text())
            self.assertEqual(result["ingest"], second_result)

    def test_replay_requires_zero_rows_added(self):
        counts = {"rows": 2, "labeled_rows": 1, "duplicate_keys": 0}
        result = {"status": "already_ingested", "release_id": "test", "geometry_counts": counts, "rows_added": 1}
        with self.assertRaises(ValueError):
            geometry_series.accept_ingest(result, "test", counts, replay=True)
