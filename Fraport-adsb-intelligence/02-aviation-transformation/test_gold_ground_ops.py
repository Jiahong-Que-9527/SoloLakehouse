"""Synthetic Silver fixtures for the gold/ground_ops taxi-in labels (02 M2)."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

import gold_ground_ops
import silver_v2

DAY = "2030-01-01"
DAY_STAMP = int(datetime(2030, 1, 1, tzinfo=timezone.utc).timestamp())
T = DAY_STAMP


class GroundOpsTests(unittest.TestCase):
    def setUp(self):
        self.workspace = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="gold-ground-ops-")))
        self.silver = self.workspace / "silver"
        self.output = self.workspace / "out"
        self.silver.mkdir()
        self.build_silver()
        self.run_main()

    def observation(self, icao, t, alt, dist):
        return {"day_utc": datetime.fromtimestamp(t, timezone.utc).date(), "icao24": icao,
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

    def test_monthly_observations_cross_midnight_without_importing_neighbor_flights(self):
        month = self.workspace / "month"
        month.mkdir()
        daily = self.workspace / "daily"
        february = daily / "2030-02-01"
        february.mkdir(parents=True)
        (february / "run_manifest.json").write_text(json.dumps({"dates_utc": [february.name]}))
        jan31, feb1 = (T + days * 86400 for days in (30, 31))
        obs_schema = pa.schema(silver_v2.SCHEMAS["observations"])
        observations = [
            self.observation("aaa001", jan31 - 120, 100, 5000),
            self.observation("aaa001", jan31 - 60, None, 500),
            self.observation("aaa001", jan31 + 60, None, 300),
            self.observation("bbb002", feb1 - 120, 100, 5000),
            self.observation("bbb002", feb1 - 60, None, 500),
        ]
        pq.write_table(pa.Table.from_pylist(observations, schema=obs_schema),
                       month / "observations.parquet")
        pq.write_table(pa.Table.from_pylist(
            [self.observation("bbb002", feb1 + 60, None, 300)], schema=obs_schema),
            february / "observations.parquet")
        flights_schema = pa.schema(silver_v2.SCHEMAS["flights"])

        def flight(icao, anchor):
            return {"day_utc": datetime.fromtimestamp(anchor, timezone.utc).date(),
                    "icao24": icao, "lastseen_epoch_s": anchor,
                    "estdepartureairport": "EDDM", "estarrivalairport": "EDDF"}

        pq.write_table(pa.Table.from_pylist([
            flight("aaa001", jan31 - 60), flight("bbb002", feb1 - 60),
        ], schema=flights_schema), month / "flights.parquet")
        pq.write_table(pa.Table.from_pylist([
            flight("bbb002", feb1 + 60),
        ], schema=flights_schema), february / "flights.parquet")
        (month / "run_manifest.json").write_text(json.dumps({
            "schema_version": "silver-month-v1",
            "requested_dates_utc": ["2030-01-29", "2030-01-30", "2030-01-31"],
            "dates_utc": ["2030-01-30", "2030-01-31"],
        }))
        output = self.workspace / "monthly-gold"
        argv = ["gold_ground_ops.py", "--silver-root", str(month), "--daily-root", str(daily),
                "--date", "2030-01-29", "--date", "2030-01-30", "--date", "2030-01-31",
                "--output", str(output)]
        with patch.object(sys, "argv", argv):
            gold_ground_ops.main()
        arrivals = pq.read_table(output / "arrivals.parquet").to_pylist()
        self.assertEqual([(str(a["day_utc"]), a["status"], a["taxi_in_s"]) for a in arrivals],
                         [("2030-01-30", "labeled", 120), ("2030-01-31", "labeled", 120)])
        manifest = json.loads((output / "run_manifest.json").read_text())
        self.assertEqual(manifest["missing_dates_utc"], ["2030-01-29"])
        self.assertEqual(list(manifest["boundary_observation_manifests"]), ["2030-02-01"])

        argv[-1] = str(self.workspace / "missing-context")
        (february / "run_manifest.json").unlink()
        with patch.object(sys, "argv", argv):
            gold_ground_ops.main()
        missing_output = Path(argv[-1])
        manifest = json.loads((missing_output / "run_manifest.json").read_text())
        self.assertEqual(manifest["missing_observation_dates_utc"], ["2030-02-01"])
        arrivals = pq.read_table(missing_output / "arrivals.parquet").to_pylist()
        self.assertEqual(arrivals[-1]["status"], "censored_few_points")

    def test_geometry_recovers_outside_points_and_requires_distinct_updates(self):
        points = [
            self.observation("aaa001", T + 10, 100, 4500),
            self.observation("aaa001", T + 20, None, 1700),
            self.observation("aaa001", T + 21, None, 1700),
            self.observation("aaa001", T + 30, None, 1600),
            self.observation("aaa001", T + 40, None, 1500),
            self.observation("aaa001", T + 50, None, 1400),
        ]
        points[2]["lastposupdate_epoch_s"] = T + 20

        def geometry(xy, *, with_stands):
            self.assertEqual(len(xy), 5)
            self.assertFalse(with_stands)
            return (np.array([[200], [200], [200], [5], [200]]),
                    np.array([5, 5, 200, 5, 200]), None,
                    np.array([False, False, True, False, False]))

        gold_ground_ops.mark_mapped_surface(points, geometry)
        self.assertEqual([p.get("on_mapped_surface") for p in points],
                         [None, True, True, True, False, False])
        legacy = gold_ground_ops.label_arrival(points, T + 20)
        self.assertEqual(legacy["status"], "censored_few_points")

        repeated = gold_ground_ops.label_arrival(points[:3], T + 20, use_geometry=True)
        self.assertEqual(repeated["status"], "censored_few_points")
        labeled = gold_ground_ops.label_arrival(points, T + 20, use_geometry=True)
        self.assertEqual(labeled["status"], "labeled")
        self.assertEqual(labeled["taxi_in_s"], 10)


if __name__ == "__main__":
    unittest.main()
