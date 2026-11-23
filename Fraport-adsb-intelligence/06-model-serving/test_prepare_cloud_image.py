import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from prepare_cloud_image import prepare_context


class CloudImageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.release = root / "release"
        self.release.mkdir()
        self.trusted = root / "trusted.json"
        self.output = root / "context"
        self.model = b"synthetic artifact"
        self.manifest = json.dumps({"schema_version": "fraport-model-release-v1", "model_release_id": "fixture",
                                    "artifact": {"path": "model.pkl", "sha256": hashlib.sha256(self.model).hexdigest()}})
        self.trusted.write_text(self.manifest)
        (self.release / "manifest.json").write_text(self.manifest)
        (self.release / "model.pkl").write_bytes(self.model)
        (self.release / "unrelated.parquet").touch()

    def test_context_contains_only_pinned_image_inputs(self):
        receipt = prepare_context(self.release, self.trusted, self.output)
        manifest_sha256 = hashlib.sha256(self.manifest.encode()).hexdigest()
        self.assertEqual(receipt["model_manifest_sha256"], manifest_sha256)
        self.assertEqual((self.output / "release/model.pkl").read_bytes(), self.model)
        self.assertEqual({file.name for file in (self.output / "release").iterdir()}, {"manifest.json", "model.pkl"})
        self.assertIn(f"ENV MODEL_MANIFEST_SHA256={manifest_sha256}", (self.output / "Dockerfile").read_text())
        with self.assertRaises(FileExistsError):
            prepare_context(self.release, self.trusted, self.output)

    def test_mismatched_pin_or_model_creates_no_context(self):
        (self.release / "model.pkl").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "model bytes"):
            prepare_context(self.release, self.trusted, self.output)
        (self.release / "manifest.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "manifest differs"):
            prepare_context(self.release, self.trusted, self.output)
        self.assertFalse(self.output.exists())
