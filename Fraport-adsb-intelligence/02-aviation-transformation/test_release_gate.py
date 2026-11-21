"""Synthetic gold fixtures for the Release Gate (02 M3, ADR-003)."""
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq

import gold_ground_ops
import release_gate

DAY = "2030-01-01"
DAY_STAMP = int(datetime(2030, 1, 1, tzinfo=timezone.utc).timestamp())
T = DAY_STAMP
CONTRACT = Path(release_gate.__file__).resolve().parent / "contracts" / "ground_ops.yaml"


def arrival(icao, flight_key, status, taxi_in_s=None):
    return {"day_utc": datetime.fromisoformat(DAY).date(), "flight_key": flight_key,
            "icao24": icao, "callsign": "DLH1AB", "lastseen_epoch_s": T,
            "touchdown_estimate_epoch_s": T if taxi_in_s is not None else None,
            "surface_start_epoch_s": T if taxi_in_s is not None else None,
            "taxi_end_epoch_s": T + taxi_in_s if taxi_in_s is not None else None,
            "taxi_in_s": taxi_in_s, "surface_point_count": 5 if taxi_in_s else 0,
            "taxi_path_m": 900.0 if taxi_in_s else None,
            "mean_surface_gap_s": 20.0 if taxi_in_s else None,
            "max_surface_gap_s": 40.0 if taxi_in_s else None,
            "end_distance_m": 300.0 if taxi_in_s else None, "status": status}


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.workspace = Path(tempfile.mkdtemp(prefix="release-gate-"))
        self.gold = self.workspace / "gold"
        self.gold.mkdir()
        self.output = self.workspace / "release"
        self.build_gold()

    def build_gold(self, rows=None):
        rows = rows if rows is not None else [
            arrival("aaa001", "aaa001:1", "labeled", taxi_in_s=360),
            arrival("bbb002", "bbb002:2", "labeled", taxi_in_s=600),
            arrival("ccc003", "ccc003:3", "no_surface"),
        ]
        schema = pa.schema([f for f in gold_ground_ops.SCHEMAS["arrivals"]])
        pq.write_table(pa.Table.from_pylist(rows, schema=schema),
                       self.gold / "arrivals.parquet")
        meta = {"schema_version": gold_ground_ops.SCHEMA_VERSION, "adr": "ADR-006",
                "dates_utc": [DAY], "policy": {}}
        meta["input_id"] = hashlib.sha256(
            json.dumps(meta, sort_keys=True).encode()).hexdigest()
        artifacts = {"arrivals.parquet": {"rows": len(rows),
                                          "sha256": release_gate.digest(
                                              self.gold / "arrivals.parquet")}}
        meta["outputs"] = artifacts
        (self.gold / "run_manifest.json").write_text(
            json.dumps(meta, indent=2, sort_keys=True) + "\n")
        (self.gold / "coverage_report.md").write_text("# coverage\n")

    def run_main(self, output=None, expect_success=True):
        argv = ["release_gate.py", "--gold-root", str(self.gold),
                "--contract", str(CONTRACT), "--output", str(output or self.output),
                "--release-id", "v001", "--approver", "test", "--notes", "synthetic"]
        with patch.object(sys, "argv", argv):
            if expect_success:
                release_gate.main()
            else:
                with self.assertRaises(SystemExit) as ctx:
                    release_gate.main()
                return ctx.exception.code

    def test_passed_release_layout(self):
        self.run_main()
        for name in ("data/part-0001.parquet", "manifest.json", "contract.yaml",
                     "validation.json", "approval.json", "_SUCCESS"):
            self.assertTrue((self.output / name).is_file(), name)
        manifest = json.loads((self.output / "manifest.json").read_text())
        self.assertEqual(manifest["release_id"], "v001")
        self.assertEqual(manifest["data_product"], "ground-ops")
        self.assertEqual(manifest["field_policy"], {"icao24": "keep", "callsign": "keep"})
        self.assertIn("data/part-0001.parquet", manifest["files"])
        validation = json.loads((self.output / "validation.json").read_text())
        self.assertEqual(validation["status"], "passed")
        self.assertTrue(all(c["passed"] for c in validation["checks"]))
        approval = json.loads((self.output / "approval.json").read_text())
        self.assertEqual(approval["approver"], "test")
        # _SUCCESS written last: its mtime is not older than any other file.
        success_time = (self.output / "_SUCCESS").stat().st_mtime_ns
        for other in self.output.rglob("*"):
            if other.name != "_SUCCESS" and other.is_file():
                self.assertLessEqual(other.stat().st_mtime_ns, success_time, other.name)

    def test_repeat_release_is_byte_identical(self):
        self.run_main()
        second = self.workspace / "release-2"
        self.run_main(output=second)
        for name in ("data/part-0001.parquet", "contract.yaml"):
            self.assertEqual(
                release_gate.digest(self.output / name),
                release_gate.digest(second / name), name)

    def test_blocked_fixture(self):
        # A contract violation: only one labeled row out of five (ratio 0.2
        # against a 0.5 floor) and one labeled row without a taxi-in label.
        rows = [arrival("aaa001", "aaa001:1", "labeled", taxi_in_s=360),
                arrival("bbb002", "bbb002:2", "no_surface"),
                arrival("ccc003", "ccc003:3", "no_surface"),
                arrival("ddd004", "ddd004:4", "no_airborne_approach"),
                arrival("eee005", "eee005:5", "no_airborne_approach")]
        self.build_gold(rows=rows)
        code = self.run_main(expect_success=False)
        self.assertEqual(code, 1)
        self.assertFalse((self.output / "_SUCCESS").exists())
        self.assertFalse((self.output / "approval.json").exists())
        validation = json.loads((self.output / "validation.json").read_text())
        self.assertEqual(validation["status"], "blocked")
        failed = {c["name"] for c in validation["checks"] if not c["passed"]}
        self.assertIn("label_coverage", failed)

    def test_blocked_taxi_in_out_of_range(self):
        rows = [arrival("aaa001", "aaa001:1", "labeled", taxi_in_s=4000),
                arrival("bbb002", "bbb002:2", "labeled", taxi_in_s=600)]
        self.build_gold(rows=rows)
        self.run_main(expect_success=False)
        validation = json.loads((self.output / "validation.json").read_text())
        self.assertEqual(validation["status"], "blocked")
        failed = {c["name"] for c in validation["checks"] if not c["passed"]}
        self.assertIn("taxi_in_range", failed)

    def test_tampered_gold_input_is_rejected_before_staging(self):
        self.build_gold()
        data = bytearray((self.gold / "arrivals.parquet").read_bytes())
        data[-1] ^= 0xFF
        (self.gold / "arrivals.parquet").write_bytes(bytes(data))
        argv = ["release_gate.py", "--gold-root", str(self.gold),
                "--contract", str(CONTRACT), "--output", str(self.output),
                "--release-id", "v001", "--approver", "test"]
        with patch.object(sys, "argv", argv):
            with self.assertRaises(SystemExit):
                release_gate.main()
        self.assertFalse(self.output.exists())

    def test_output_guardrails(self):
        self.run_main()
        # Existing output directory is refused.
        argv = ["release_gate.py", "--gold-root", str(self.gold),
                "--contract", str(CONTRACT), "--output", str(self.output),
                "--release-id", "v002", "--approver", "test"]
        with patch.object(sys, "argv", argv):
            with self.assertRaises(SystemExit):
                release_gate.main()


if __name__ == "__main__":
    unittest.main()
