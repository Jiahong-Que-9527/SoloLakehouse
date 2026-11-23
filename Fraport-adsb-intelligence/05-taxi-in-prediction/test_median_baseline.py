"""Check chronological split, label maturity, coverage and artifact integrity."""

import json
import tempfile
import unittest
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from median_baseline import evaluate, load_dataset, sha256


def example(key, when, label, status=None):
    return {"prediction_id": key, "trigger_event_at": when - 5, "prediction_at": when,
            "match_status": status or ("matched_labeled" if label is not None else "unmatched"),
            "taxi_in_s": label}


class MedianBaselineTests(unittest.TestCase):
    def test_cutoff_is_inclusive_for_holdout_and_embargoes_immature_train_label(self):
        rows = [example("e", 10001, 70), example("a", 1000, 100),
                example("b", 2000, 200), example("c", 9999, 2700),
                example("d", 10000, 180), example("f", 10002, None)]
        report = evaluate(rows, cutoff=10000, label_match_window_s=90)
        self.assertEqual(report["model"]["prediction_seconds"], 150)
        self.assertEqual(report["train"], {"predictions": 3, "used_labels": 2, "embargoed_labels": 1})
        self.assertEqual(report["holdout"]["predictions"], 3)
        self.assertEqual(report["holdout"]["evaluated_labels"], 2)
        self.assertEqual(report["holdout"]["label_coverage"], 2 / 3)
        self.assertEqual(report["metrics_seconds"]["mae"], 55)
        self.assertEqual(report["metrics_seconds"]["bias_prediction_minus_actual"], 25)

    def test_labels_are_rejected_when_outcome_status_disagrees(self):
        with self.assertRaisesRegex(ValueError, "invalid taxi-in target or label status"):
            evaluate([example("bad", 1000, 100, "unmatched")], cutoff=10000, label_match_window_s=90)

    def test_dataset_is_pinned_by_manifest_and_payload_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            payload = path / "training.parquet"
            pq.write_table(pa.Table.from_pylist([example("a", 1000, 100)]), payload)
            manifest = {"label_release": {"label_version": "taxi-in-geometry-v2"}, "predictions": 1,
                        "files": {"training.parquet": {"sha256": sha256(payload), "rows": 1}}}
            (path / "manifest.json").write_text(json.dumps(manifest))
            _, manifest_sha, rows = load_dataset(path)
            self.assertEqual(manifest_sha, sha256(path / "manifest.json"))
            self.assertEqual(rows[0]["taxi_in_s"], 100)
            payload.write_bytes(b"replaced payload")
            with self.assertRaisesRegex(ValueError, "checksum does not match"):
                load_dataset(path)
