"""Synthetic Silver fixtures for the gold/ground_ops taxi-in labels (02 M2)."""
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
import silver_v2

DAY = "2030-01-01"
DAY_STAMP = int(datetime(2030, 1, 1, tzinfo=timezone.utc).timestamp())
T = DAY_STAMP


class GroundOpsTests(unittest.TestCase):
    def setUp(self):
        self.workspace = Path(tempfile.mkdtemp(prefix="gold-ground-ops-"))
        self.silver = self.workspace / "silver"
        self.output = self.workspace / "out"
        self.silver.mkdir()
        self.build_silver()
        self.run_main()

    def observation(self, icao, t, alt, dist):
        return {"day_utc": datetime.fromisoformat(DAY).date(), "icao24": icao,
                "time_epoch_s": t, "lastposupdate_epoch_s": t, "position_age_s": 0,
                "lat": 50.0, "lon": 8.5, "baroaltitude_m": None, "geoaltitude_m": alt,
                "velocity_mps": None, "heading_deg": None, "vertrate_mps": None,
                "onground_raw": alt is None, "callsign": None,
                "airport_ref_distance_m": dist, "segment_no": 1}

    def build_silver(self):
        observations = []
        # arrival-1: labeled. Airborne approach, touchdown ~T+1200, taxi 6 min.
        for i, alt in enumerate((900, 400, 150, 60)):
            observations.append(self.observation("aaa001", T+900 + i*30, alt, 12000 - i*3000))
        for i, t in enumerate((T+1200, T+1260, T+1320, T+1500, T+1560)):
            observations.append(self.observation("aaa001", t, None, 500 + (4 - i) * 100))
        # arrival-2: no surface points at all.
        observations.append(self.observation("bbb002", T+1800, 500, 9000))
        # arrival-3: surface without an airborne approach (already on ground).
        observations.append(self.observation("ccc003", T+2400, None, 300))
        observations.append(self.observation("ccc003", T+2460, None, 300))
        # arrival-4: censored (airborne approach observed, but a single surface point).
        observations.append(self.observation("ddd004", T+3500, 120, 4000))
        observations.append(self.observation("ddd004", T+3620, None, 400))
        # phantom turnaround: EDDF -> EDDF must be excluded from candidates.
        observations.append(self.observation("phantom", T+1000, None, 200))
        silver_v2.SCHEMAS  # keep import meaning visible
        schema = pa.schema([f for f in silver_v2.SCHEMAS["observations"]])
        pq.write_table(pa.Table.from_pylist(observations, schema=schema),
                       self.silver / "observations.parquet")
        flights = [
            {"day_utc": datetime.fromisoformat(DAY).date(), "icao24": "aaa001",
             "callsign": "DLH1AB", "firstseen_epoch_s": T, "lastseen_epoch_s": T+1200,
             "estdepartureairport": "EDDM", "estarrivalairport": "EDDF"},
            {"day_utc": datetime.fromisoformat(DAY).date(), "icao24": "bbb002",
             "callsign": "DLH2CD", "firstseen_epoch_s": T, "lastseen_epoch_s": T+1800,
             "estdepartureairport": "EDDM", "estarrivalairport": "EDDF"},
            {"day_utc": datetime.fromisoformat(DAY).date(), "icao24": "ccc003",
             "callsign": "DLH3EF", "firstseen_epoch_s": T, "lastseen_epoch_s": T+2400,
             "estdepartureairport": "EDDM", "estarrivalairport": "EDDF"},
            {"day_utc": datetime.fromisoformat(DAY).date(), "icao24": "ddd004",
             "callsign": "DLH4GH", "firstseen_epoch_s": T, "lastseen_epoch_s": T+3600,
             "estdepartureairport": "EDDM", "estarrivalairport": "EDDF"},
            {"day_utc": datetime.fromisoformat(DAY).date(), "icao24": "phantom",
             "callsign": "PHANTOM", "firstseen_epoch_s": T, "lastseen_epoch_s": T+1000,
             "estdepartureairport": "EDDF", "estarrivalairport": "EDDF"},
        ]
        fschema = pa.schema([f for f in silver_v2.SCHEMAS["flights"]])
        pq.write_table(pa.Table.from_pylist(flights, schema=fschema),
                       self.silver / "flights.parquet")

    def run_main(self):
        with patch.object(sys, "argv", ["gold_ground_ops.py", "--silver-root", str(self.silver),
                                        "--date", DAY, "--output", str(self.output)]):
            gold_ground_ops.main()

    def read(self, name):
        return pq.read_table(self.output / f"{name}.parquet").to_pylist()

    def test_statuses_and_label(self):
        arrivals = {a["icao24"]: a for a in self.read("arrivals")}
        self.assertNotIn("phantom", arrivals)
        labeled = arrivals["aaa001"]
        self.assertEqual(labeled["status"], "labeled")
        self.assertEqual(labeled["touchdown_estimate_epoch_s"], T+990)
        self.assertEqual(labeled["surface_start_epoch_s"], T+1200)
        self.assertEqual(labeled["taxi_end_epoch_s"], T+1560)
        self.assertEqual(labeled["taxi_in_s"], 360)
        self.assertEqual(arrivals["bbb002"]["status"], "no_surface")
        self.assertEqual(arrivals["ccc003"]["status"], "no_airborne_approach")
        self.assertEqual(arrivals["ddd004"]["status"], "censored_few_points")

        manifest = json.loads((self.output / "run_manifest.json").read_text())
        self.assertEqual(manifest["schema_version"], "gold-ground-ops-v1")
        report = (self.output / "coverage_report.md").read_text()
        self.assertIn("labeled", report)


if __name__ == "__main__":
    unittest.main()
