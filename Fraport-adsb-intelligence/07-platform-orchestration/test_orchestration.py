import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq
import duckdb
from dagster import AssetKey, DagsterInstance, SkipReason

from orchestration import defs, geometry_release_ready, release_inputs


class LocalOrchestrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.state = root / "state"
        self.instance_dir = root / "instance"
        self.instance_dir.mkdir()
        (self.instance_dir / "dagster.yaml").write_text("telemetry:\n  enabled: false\n")
        self.release = root / "releases" / "geometry-v2-2024-11"
        (self.release / "data").mkdir(parents=True)
        self.checkpoint = self.state / "handoffs" / f"{self.release.name}.json"
        self.enterContext(patch.dict(os.environ, {
            "FRAPORT_RELEASES_DIR": str(self.release.parent), "FRAPORT_STATE_DIR": str(self.state),
        }))
        self.enterContext(patch("orchestration.source_commit", return_value="a" * 40))
        day = date(2024, 11, 1)
        lastseen = 1730419500
        labels = pa.Table.from_pylist([{
            "day_utc": day, "icao24": "aaaaaa", "lastseen_epoch_s": lastseen,
            "flight_key": f"aaaaaa:{lastseen}", "touchdown_estimate_epoch_s": lastseen - 400,
            "surface_start_epoch_s": lastseen - 300, "taxi_end_epoch_s": lastseen, "taxi_in_s": 300,
            "status": "labeled",
        }], schema=release_inputs.INPUT_SCHEMA)
        pq.write_table(labels, self.release / "data/part-0001.parquet")
        (self.release / "contract.yaml").write_text("fixture: true\n")
        files = {name: {"sha256": release_inputs.file_digest(self.release / name)} for name in release_inputs.PAYLOADS}
        files["data/part-0001.parquet"]["rows"] = len(labels)
        self.write_control("manifest.json", data_product="ground-ops", contract_version="2",
                           release_schema_version="release-v1", schema_version="gold-ground-ops-v1",
                           label_version="taxi-in-geometry-v2", grain=list(release_inputs.EVENT_KEY),
                           files=files, created_at="2024-12-01T00:00:00+00:00")
        self.write_control("validation.json", status="passed")
        self.write_control("approval.json", approver="fixture", contract_version="2")
        self.write_control("_SUCCESS")

    def write_control(self, name: str, **payload):
        (self.release / name).write_text(json.dumps({"release_id": self.release.name, **payload}))

    def execute(self, instance, job_name):
        return defs.resolve_job_def(job_name).execute_in_process(
            instance=instance, partition_key="2024-11", raise_on_error=False,
        )

    def test_failed_handoff_resumes_from_verified_gold_and_is_idempotent(self):
        self.checkpoint.mkdir(parents=True)
        with DagsterInstance.local_temp(str(self.instance_dir)) as instance:
            failed = self.execute(instance, "verify_month")
            self.assertFalse(failed.success)
            self.assertTrue(failed.is_node_success("approved_gold"))
            self.assertTrue(any(event.event_type_value == "STEP_UP_FOR_RETRY" for event in failed.all_events))
            self.checkpoint.rmdir()

        with DagsterInstance.local_temp(str(self.instance_dir)) as instance:
            restored = self.execute(instance, "resume_local_handoff")
            self.assertTrue(restored.success)
            self.assertTrue(restored.is_node_success("local_handoff"))
            self.assertEqual(len(instance.fetch_materializations(AssetKey("approved_gold"), limit=10).records), 1)
            raw = self.checkpoint.read_bytes()
            self.assertTrue(self.execute(instance, "resume_local_handoff").success)
            self.assertEqual(self.checkpoint.read_bytes(), raw)
            evidence = json.loads(raw)
            self.assertEqual(evidence["status"], "verified_local")
            self.assertEqual(evidence["coverage_status_counts"], {"labeled": 1})
            self.assertEqual(evidence["source_commit"], "a" * 40)

            self.write_control("approval.json", approver="different", contract_version="2")
            self.assertFalse(self.execute(instance, "resume_local_handoff").success)
            self.assertEqual(self.checkpoint.read_bytes(), raw)

    def test_missing_commit_marker_stops_before_checkpoint(self):
        (self.release / "_SUCCESS").unlink()
        with DagsterInstance.local_temp(str(self.instance_dir)) as instance:
            self.assertFalse(self.execute(instance, "verify_month").success)
            self.assertEqual(len(instance.fetch_materializations(AssetKey("approved_gold"), limit=10).records), 0)
        self.assertFalse(self.checkpoint.exists())

    def test_sensor_skips_incomplete_releases_and_reuses_the_same_run_key(self):
        (self.release / "_SUCCESS").unlink()
        self.assertIsInstance(geometry_release_ready(), SkipReason)
        self.write_control("_SUCCESS")
        first, = geometry_release_ready()
        repeat, = geometry_release_ready()
        self.assertEqual(first.partition_key, "2024-11")
        self.assertEqual(first.run_key, repeat.run_key)
        self.assertTrue(first.run_key.startswith("geometry-v2-2024-11:"))

    def test_local_ingestion_and_reconciliation_are_idempotent(self):
        database = self.state / "analytics.duckdb"
        with DagsterInstance.local_temp(str(self.instance_dir)) as instance:
            first = self.execute(instance, "ingest_month_local")
            self.assertTrue(first.success)
            repeat = self.execute(instance, "resume_local_analytics")
            self.assertTrue(repeat.success)
            loaded = first.output_for_node("local_analytics")
            replayed = repeat.output_for_node("local_analytics")
            self.assertEqual(loaded["status"], "ingested")
            self.assertEqual(loaded["rows_added"], 1)
            self.assertEqual(replayed["status"], "already_ingested")
            self.assertEqual(replayed["rows_added"], 0)
            self.assertEqual(replayed["geometry_counts"], {"rows": 1, "labeled_rows": 1, "duplicate_keys": 0})
            self.assertEqual(len(instance.fetch_materializations(AssetKey("approved_gold"), limit=10).records), 1)
            with duckdb.connect(str(database), config={"threads": 2}) as connection:
                self.assertEqual(connection.execute("SELECT count(*) FROM ingest_ledger").fetchone(), (1,))
                connection.execute("DELETE FROM ground_ops_arrivals_geometry_v2")
            self.assertFalse(self.execute(instance, "resume_local_analytics").success)

    def test_analytics_rechecks_payload_after_handoff(self):
        with DagsterInstance.local_temp(str(self.instance_dir)) as instance:
            self.assertTrue(self.execute(instance, "verify_month").success)
            (self.release / "data/part-0001.parquet").write_bytes(b"changed after verification")
            self.assertFalse(self.execute(instance, "resume_local_analytics").success)
        self.assertFalse((self.state / "analytics.duckdb").exists())

    def test_bigquery_reconciliation_never_calls_cloud_if_gold_changes_after_handoff(self):
        with DagsterInstance.local_temp(str(self.instance_dir)) as instance:
            self.assertTrue(self.execute(instance, "verify_month").success)
            (self.release / "data/part-0001.parquet").write_bytes(b"changed after verification")
            with patch("orchestration.reconcile_existing_release") as reconcile:
                self.assertFalse(self.execute(instance, "reconcile_month_bigquery").success)
                reconcile.assert_not_called()


if __name__ == "__main__":
    unittest.main()
