"""Check that model registration requires matching replay and quality evidence."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from model_release import release_payload, sha256, verify_replay

IMAGE = "sha256:" + "a" * 64
COMMIT = "b" * 40


class ModelReleaseTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.candidate = self.root / "candidate"
        self.evaluation = self.root / "evaluation"
        self.candidate.mkdir()
        self.evaluation.mkdir()
        model = self.candidate / "model.pkl"
        model.write_bytes(b"example candidate")
        shared = {"candidate_id": "boosted-example", "model_sha256": sha256(model),
                  "baseline_id": "median-example", "baseline_report_sha256": "baseline-hash",
                  "mae_improvement_seconds": 2.0}
        self.write(self.candidate / "candidate-report.json", {
            **shared, "feature_columns": ["feature"], "label_release_id": "geometry-v2-2024-11",
            "feature_dataset_id": "training-features", "feature_manifest_sha256": "training-hash",
            "holdout_metrics_seconds": {"mae": 1.0},
        })
        self.write(self.evaluation / "evaluation-report.json", {
            **shared, "training_manifest_sha256": "training-hash",
            "evaluation_label_release_id": "geometry-v2-2024-12",
            "evaluation_dataset_id": "evaluation-features", "evaluation_manifest_sha256": "evaluation-hash",
            "availability": {"mode": "simulated_fixed_delay"}, "candidate_metrics_seconds": {"mae": 2.0},
            "baseline_metrics_seconds": {"mae": 4.0},
        })
        self.replay = self.root / "replay"
        self.copy_replay()

    @staticmethod
    def write(path, data):
        path.write_text(json.dumps(data))

    def copy_replay(self):
        for directory in (self.candidate, self.evaluation):
            shutil.copytree(directory, self.replay / directory.name, dirs_exist_ok=True)

    def evidence(self):
        return verify_replay(self.candidate, self.evaluation, self.replay, IMAGE, COMMIT)

    def test_identical_container_replay_releases_a_candidate(self):
        result = release_payload(self.candidate, self.evaluation, self.evidence())
        self.assertEqual(result["stage"], "candidate")
        self.assertEqual(result["source_commit"], COMMIT)
        self.assertEqual(result["artifact"]["sha256"], sha256(self.candidate / "model.pkl"))

    def test_a_changed_replay_artifact_blocks_registration(self):
        (self.replay / "candidate" / "model.pkl").write_bytes(b"different")
        with self.assertRaisesRegex(ValueError, "container replay differs.*model"):
            self.evidence()

    def test_a_losing_evaluation_cannot_pass_even_when_reproduced(self):
        path = self.evaluation / "evaluation-report.json"
        result = json.loads(path.read_text())
        result["mae_improvement_seconds"] = -1.0
        self.write(path, result)
        self.copy_replay()
        with self.assertRaisesRegex(ValueError, "beat the frozen median"):
            release_payload(self.candidate, self.evaluation, self.evidence())
