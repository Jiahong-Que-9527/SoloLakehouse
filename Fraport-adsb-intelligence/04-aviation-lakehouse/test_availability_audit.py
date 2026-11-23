import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from availability_audit import RECEIPT_COLUMN, audit
from feature_replay import epoch
from release_inputs import file_digest


class AvailabilityAuditTests(unittest.TestCase):
    start = date(2025, 4, 1)
    until = start + timedelta(days=1)
    prior = start - timedelta(days=1)

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.silver = Path(directory.name)

    def publish(self, day, rows, *, has_receipt=True, has_provenance=True):
        folder = self.silver / day.isoformat()
        folder.mkdir()
        table = pa.Table.from_pylist(rows)
        if not has_receipt:
            table = table.drop([RECEIPT_COLUMN])
        parquet = folder / "observations.parquet"
        pq.write_table(table, parquet)
        manifest = {"schema_version": "silver-eddf-v2", "dates_utc": [day.isoformat()],
                    "outputs": {parquet.name: {"sha256": file_digest(parquet)}}}
        if has_provenance:
            manifest["availability"] = {"mode": "observed", "recorded_at": "feature_input",
                                        "timestamp_column": RECEIPT_COLUMN, "source": "fixture", "clock": "fixture"}
        (folder / "run_manifest.json").write_text(json.dumps(manifest))

    def observation(self, event, receipt, ground, aircraft="aaaaaa", speed=75.0):
        start = epoch(self.start)
        return {"icao24": aircraft, "time_epoch_s": start + event, RECEIPT_COLUMN: start + receipt,
                "onground_raw": ground, "velocity_mps": speed, "geoaltitude_m": 100.0,
                "vertrate_mps": -2.0, "airport_ref_distance_m": 1100.0}

    def test_missing_receipt_and_unattested_column_block_the_audit(self):
        self.publish(self.prior, [self.observation(-5, -4, False)], has_receipt=False)
        self.publish(self.start, [self.observation(0, 5, True)], has_provenance=False)
        report = audit(self.silver, self.start, self.until)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["partition_counts"], {"missing_receipt_column": 1, "missing_observed_provenance": 1})

    def test_measured_replay_counts_late_rows_and_changed_features(self):
        self.publish(self.prior, [self.observation(-10, -9, False), self.observation(-1, 30, False, speed=95.0)])
        self.publish(self.start, [self.observation(3, 4, True),
                                  self.observation(10, 90, False, "bbbbbb"),
                                  self.observation(50, 70, True, "bbbbbb")])
        report = audit(self.silver, self.start, self.until)
        self.assertEqual(report["status"], "measured")
        self.assertEqual(report["observation_delays"]["observations"], 3)
        self.assertEqual(report["observation_delays"]["p95_seconds"], 80)
        self.assertEqual(report["arrival_triggers"], {"observed": 1, "simulated": 2, "shared": 1,
                         "simulated_only": 1, "observed_only": 0, "shared_with_changed_features": 1,
                         "observed_within_simulated_delay": 1})

    def test_receipt_before_event_blocks_even_on_context_day(self):
        self.publish(self.prior, [self.observation(-5, -6, False)])
        self.publish(self.start, [self.observation(0, 5, True)])
        report = audit(self.silver, self.start, self.until)
        self.assertEqual(report["reason"], "invalid_measured_timestamps")
        self.assertEqual(report["observation_delays"]["invalid_timestamps_including_context"], 1)


if __name__ == "__main__":
    unittest.main()
