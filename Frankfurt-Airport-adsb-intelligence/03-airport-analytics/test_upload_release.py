"""Exercise a create-only Landing upload and the recovery path."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from google.api_core.exceptions import PreconditionFailed

from test_ingest_release import build_release
from upload_release import upload_release


class UploadReleaseTests(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.release = build_release(Path(workspace.name))
        for name in ("approval.json", "_SUCCESS"):
            (self.release / name).write_text(json.dumps({"release_id": "v002"}))
        self.writer = Mock()
        self.writer.name = "test-landing"
        self.reader = Mock()
        self.objects = {}

        def create(name):
            def upload(path, *, if_generation_match):
                self.assertEqual(if_generation_match, 0)
                if name in self.objects:
                    raise PreconditionFailed("object already exists")
                self.objects[name] = path.read_bytes()

            return Mock(upload_from_filename=upload)

        def read(name):
            return Mock(download_to_file=lambda stream: stream.write(self.objects[name]))

        self.writer.blob.side_effect = create
        self.reader.blob.side_effect = read

    def test_resume_partial_release_and_reuse_completed_release(self):
        contract = "releases/v002/contract.yaml"
        self.objects[contract] = (self.release / "contract.yaml").read_bytes()
        first = upload_release(self.release, self.writer, self.reader)
        self.reader.blob.assert_called_once_with(contract)
        self.assertEqual(first["reused"], ["contract.yaml"])
        self.assertEqual(first["created"][-1], "_SUCCESS")
        self.assertEqual(next(reversed(self.objects)), "releases/v002/_SUCCESS")

        repeat = upload_release(self.release, self.writer, self.reader)
        self.assertEqual(repeat["created"], [])
        self.assertEqual(len(repeat["reused"]), 6)

    def test_conflicting_object_stops_upload(self):
        self.objects["releases/v002/contract.yaml"] = b"different"
        with self.assertRaisesRegex(ValueError, "Landing checksum mismatch"):
            upload_release(self.release, self.writer, self.reader)
        self.assertEqual(self.objects, {"releases/v002/contract.yaml": b"different"})

    def test_incomplete_local_release_stops_before_upload(self):
        (self.release / "_SUCCESS").unlink()
        with self.assertRaises(FileNotFoundError):
            upload_release(self.release, self.writer, self.reader)
        self.writer.blob.assert_not_called()


if __name__ == "__main__":
    unittest.main()
