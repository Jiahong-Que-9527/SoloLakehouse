"""Synthetic release fixtures for the ingest job (03 M3)."""
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import ingest_release

DATA = b"parquet-bytes"


def build_release(root: Path, release_id="v002", data_product="ground-ops",
                  rows=3, gate_status="passed", data_bytes=DATA, **manifest_fields):
    root.mkdir(parents=True, exist_ok=True)
    data = root / "data"
    data.mkdir(exist_ok=True)
    (data / "part-0001.parquet").write_bytes(data_bytes)
    contract = root / "contract.yaml"
    contract.write_text("data_product: ground-ops\n")
    files = {
        "data/part-0001.parquet": {"rows": rows,
                                   "sha256": hashlib.sha256(data_bytes).hexdigest()},
        "contract.yaml": {"sha256": hashlib.sha256(
            contract.read_bytes()).hexdigest()},
    }
    checks = [{"name": "schema", "passed": gate_status == "passed",
               "detail": "synthetic"}]
    (root / "validation.json").write_text(json.dumps(
        {"release_id": release_id, "status": gate_status, "checks": checks}))
    (root / "manifest.json").write_text(json.dumps(
        {"release_id": release_id, "data_product": data_product,
         "files": files, **manifest_fields}, sort_keys=True) + "\n")
    return root


class FakeOps:
    instances = []
    # Class-level state simulates the real ledger table, which outlives
    # a single BigQueryOps instance.
    ledger = {}
    counts = {}

    def __init__(self, project, dataset, region):
        self.calls = []
        self.query_jobs = []
        FakeOps.instances.append(self)

    def ensure_ledger(self):
        self.calls.append("ensure_ledger")

    def already_ingested(self, release_id):
        return FakeOps.ledger.get(release_id) == "ingested"

    def ensure_table(self, table, gold_bucket, connection):
        self.calls.append(("ensure_table", table))

    def stage_external(self, table, uri):
        self.calls.append(("stage_external", uri))

    def apply_release(self, table, external, release_id, expected_rows):
        self.calls.append(("apply", release_id, expected_rows))
        return expected_rows

    def record(self, release_id, data_product, manifest_sha, row_count,
               status, reason):
        self.calls.append(("record", status, reason))
        FakeOps.ledger[release_id] = status

    def geometry_counts(self, release_id):
        self.calls.append(("geometry_counts", release_id))
        return self.counts


class IngestTests(unittest.TestCase):
    def setUp(self):
        FakeOps.instances = []
        FakeOps.ledger = {}
        FakeOps.counts = {"rows": 3, "labeled_rows": 2, "duplicate_keys": 0}
        self.workspace = Path(tempfile.mkdtemp(prefix="ingest-test-"))
        self.release = build_release(self.workspace / "release")

    def run_main(self, expect_exit=None, table=None, extra_args=()):
        argv = ["ingest_release.py", "--landing", str(self.release),
                "--project", "test-proj", "--gold-bucket", "test-gold"]
        if table:
            argv.extend(["--table", table])
        argv.extend(extra_args)
        with patch.object(sys, "argv", argv), \
             patch.object(ingest_release, "BigQueryOps", FakeOps), \
             patch.object(sys, "stdout", new_callable=io.StringIO) as stdout:
            if expect_exit is None:
                ingest_release.main()
            else:
                with self.assertRaises(SystemExit) as ctx:
                    ingest_release.main()
                self.assertEqual(ctx.exception.code, expect_exit)
            return json.loads(stdout.getvalue())

    def test_happy_path_ingests_once(self):
        self.run_main()
        ops = FakeOps.instances[0]
        self.assertEqual(ops.calls[0], "ensure_ledger")
        self.assertIn(("ensure_table", ingest_release.RADIUS_TABLE), ops.calls)
        self.assertIn(("apply", "v002", 3), ops.calls)
        self.assertIn(("record", "ingested", ""), ops.calls)

    def test_repeat_ingestion_adds_nothing(self):
        self.run_main()
        self.run_main()
        first, second = FakeOps.instances
        self.assertIn(("record", "ingested", ""), first.calls)
        self.assertEqual(second.calls, ["ensure_ledger"])
        # The second run never touched the table.
        self.assertNotIn(("ensure_table", "ground_ops_arrivals"), second.calls)
        self.assertEqual(second.ledger, {"v002": "ingested"})

    def test_geometry_uses_a_separate_table(self):
        self.release = build_release(
            self.workspace / "geometry", release_id="geometry-v2-2030-01",
            label_version=ingest_release.GEOMETRY_LABEL_VERSION, contract_version="2")
        self.run_main()
        self.assertIn(("ensure_table", ingest_release.GEOMETRY_TABLE),
                      FakeOps.instances[0].calls)

    def test_geometry_acceptance_on_first_ingest_and_repeat(self):
        self.release = build_release(
            self.workspace / "geometry", label_version=ingest_release.GEOMETRY_LABEL_VERSION,
            contract_version="2")
        args = ("--max-bytes-billed", "104857600", "--expect-geometry-labels", "2")
        first = self.run_main(extra_args=args)
        repeat = self.run_main(extra_args=args)
        self.assertEqual(first["geometry_counts"], FakeOps.counts)
        self.assertEqual(first["status"], "ingested")
        self.assertEqual(repeat["geometry_counts"], FakeOps.counts)
        self.assertEqual(repeat["rows_added"], 0)
        self.assertEqual(FakeOps.instances[1].max_bytes_billed, 104857600)
        self.assertEqual(FakeOps.instances[1].calls, ["ensure_ledger", ("geometry_counts", "v002")])

    def test_geometry_acceptance_failure_does_not_publish_ledger_record(self):
        self.release = build_release(
            self.workspace / "geometry", label_version=ingest_release.GEOMETRY_LABEL_VERSION,
            contract_version="2")
        FakeOps.counts["duplicate_keys"] = 1
        result = self.run_main(expect_exit=1, extra_args=("--expect-geometry-labels", "2"))
        self.assertEqual(result["status"], "verification_failed")
        self.assertEqual(FakeOps.ledger, {})

    def test_requested_table_cannot_mix_label_versions(self):
        self.run_main(expect_exit=1, table=ingest_release.GEOMETRY_TABLE)
        self.release = build_release(
            self.workspace / "geometry", label_version=ingest_release.GEOMETRY_LABEL_VERSION,
            contract_version="2")
        self.run_main(expect_exit=1, table=ingest_release.RADIUS_TABLE)
        self.assertEqual(FakeOps.instances, [])

    def test_unversioned_geometry_is_blocked(self):
        self.release = build_release(
            self.workspace / "experimental", input={"airport_geometry": {"files": {}}})
        self.run_main(expect_exit=1)
        self.assertEqual(FakeOps.instances, [])

    def test_failing_gate_is_blocked(self):
        self.release = build_release(self.workspace / "blocked",
                                     gate_status="blocked")
        self.run_main(expect_exit=1)
        self.assertEqual(FakeOps.instances, [])  # no BigQuery access at all

    def test_tampered_data_is_blocked(self):
        build_release(self.release)  # rebuild manifest over changed bytes
        (self.release / "data" / "part-0001.parquet").write_bytes(b"tampered")
        self.run_main(expect_exit=1)
        self.assertEqual(FakeOps.instances, [])

    def test_missing_release_file_is_blocked(self):
        (self.release / "contract.yaml").unlink()
        self.run_main(expect_exit=1)
        self.assertEqual(FakeOps.instances, [])


class BigQueryOpsTests(unittest.TestCase):
    def test_query_uses_billing_cap_and_records_job_evidence(self):
        job = Mock(job_id="pilot-job", total_bytes_billed=10_485_760)
        job.result.return_value = [{"total_rows": 3, "labeled_rows": 2, "duplicate_keys": 0}]
        with patch("google.cloud.bigquery.Client") as client:
            client.return_value.query.return_value = job
            ops = ingest_release.BigQueryOps("test-proj", "aviation", "europe-west3")
            ops.max_bytes_billed = 104_857_600
            self.assertEqual(ops.geometry_counts("geometry-v2-2024-11"),
                             {"rows": 3, "labeled_rows": 2, "duplicate_keys": 0})
            self.assertIn("AS total_rows", client.return_value.query.call_args.args[0])
            kwargs = client.return_value.query.call_args.kwargs
            self.assertEqual(kwargs["job_config"].maximum_bytes_billed, 104_857_600)
            self.assertEqual(kwargs["location"], "europe-west3")
        self.assertEqual(ops.query_jobs, [{"job_id": "pilot-job", "bytes_billed": 10_485_760}])


if __name__ == "__main__":
    unittest.main()
