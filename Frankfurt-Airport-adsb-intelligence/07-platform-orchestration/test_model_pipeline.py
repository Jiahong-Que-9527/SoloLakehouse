import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from model_pipeline import MODEL_RELEASE, REPLAY_FILES, digest, features_for, replay_model


class ModelPipelineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.state = Path(temporary.name)

    def test_existing_features_require_matching_inputs_and_payload_checksum(self):
        output = self.state / "features"
        output.mkdir()
        parquet = output / "training.parquet"
        parquet.write_bytes(b"verified features")
        pins = {"label_manifest_sha256": "label-sha", "silver_observations": [],
                "availability": {"mode": "simulated_fixed_delay", "delay_seconds": 5}, "code_sha256": {}}
        manifest = {**pins, "label_release": {"manifest_sha256": "label-sha"}, "predictions": 1,
                    "feature_dataset_id": "features-2024-11-fixture",
                    "files": {"training.parquet": {"sha256": digest(parquet)}}}
        (output / "manifest.json").write_text(json.dumps(manifest))
        with patch("model_pipeline.feature_plan", return_value=(output, pins)), patch("model_pipeline.subprocess.run") as runner:
            self.assertTrue(features_for(self.state, self.state, self.state, {}, build=True)["reused"])
            parquet.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "checksum"):
                features_for(self.state, self.state, self.state, {}, build=True)
            runner.assert_not_called()

    def test_bad_feature_manifest_blocks_container_before_launch(self):
        release = json.loads(MODEL_RELEASE.read_bytes())
        feature = {"feature_dataset_id": release["training_dataset_id"], "manifest_sha256": "changed"}
        with patch("model_pipeline.docker_replay") as runner:
            with self.assertRaisesRegex(ValueError, "training features do not match"):
                replay_model(self.state, feature, {}, self.state / "baseline.json", "docker")
            runner.assert_not_called()

    def test_training_reuses_verified_outputs_and_rejects_tampering(self):
        baseline = self.state / "baseline.json"
        baseline.write_text("frozen baseline")
        release = json.loads(MODEL_RELEASE.read_bytes())
        release["baseline_report_sha256"] = digest(baseline)
        for name, keys in REPLAY_FILES.items():
            entry = release
            for key in keys[:-1]:
                entry = entry[key]
            entry[keys[-1]] = hashlib.sha256(name.encode()).hexdigest()
        manifest = self.state / "release.json"
        manifest.write_text(json.dumps(release))
        training = {"feature_dataset_id": release["training_dataset_id"],
                    "manifest_sha256": release["training_manifest_sha256"], "directory": str(self.state)}
        evaluation = {"feature_dataset_id": release["evaluation_dataset_id"],
                      "manifest_sha256": release["evaluation_manifest_sha256"], "directory": str(self.state)}
        def simulated_replay(_docker, _image, _training, _evaluation, _baseline, output):
            for name in REPLAY_FILES:
                target = output / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(name.encode())

        with patch("model_pipeline.MODEL_RELEASE", manifest), \
             patch("model_pipeline.docker_replay", side_effect=simulated_replay) as runner:
            first = replay_model(self.state, training, evaluation, baseline, "docker")
            self.assertFalse(first["reused"])
            self.assertTrue(replay_model(self.state, training, evaluation, baseline, "docker")["reused"])
            (Path(first["directory"]) / "candidate/model.pkl").write_bytes(b"changed output")
            with self.assertRaisesRegex(ValueError, "differs from the M4 release"):
                replay_model(self.state, training, evaluation, baseline, "docker")
            runner.assert_called_once()
