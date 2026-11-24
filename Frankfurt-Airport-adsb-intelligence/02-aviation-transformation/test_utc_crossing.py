"""Synthetic UTC boundaries and occupancy evidence for the 02 CI."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

import silver_m1
from crossing_observations import apply_occupancy_alignment


MIDNIGHT = int(datetime(2030, 1, 2, tzinfo=timezone.utc).timestamp())
DAY = "2030-01-01"


class UtcSilverTests(unittest.TestCase):
    def setUp(self):
        # Keep generated fixtures in the runner's temporary area for diagnosis.
        self.workspace = Path(tempfile.mkdtemp(prefix="silver-utc-synthetic-"))
        self.bronze = self.workspace / "bronze"
        self.geometry = self.workspace / "geometry"
        self.geometry.mkdir()

    def partition(self, kind, stamp, contents):
        timestamp = datetime.fromtimestamp(stamp, timezone.utc)
        day = timestamp.date().isoformat()
        prefix, name, dataset = (
            ("hours", f"hour-{timestamp:%H}", "eddf_r75km")
            if kind == "states" else ("days", "flights", "eddf_flights")
        )
        data = self.bronze / "fixtures" / f"dt={day}" / (name + ".parquet")
        data.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.table(contents), data)
        manifest = self.bronze / "metadata/manifests" / prefix / f"dt={day}" / (name + ".json")
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({
            "dataset_id": dataset, "dataset_version": "v1", "status": "complete",
            "window_start": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "path": str(data.relative_to(self.bronze)), "sha256": silver_m1.digest(data),
        }))

    def flights(self, day_stamp, arrival_stamp, aircraft):
        self.partition("flights", day_stamp, {
            "icao24": [aircraft], "lastseen": [arrival_stamp],
            "firstseen": [arrival_stamp-600], "estarrivalairport": ["EDDF"],
        })

    def state(self, hour_stamp, epochs):
        count = len(epochs)
        self.partition("states", hour_stamp, {
            "icao24": ["aaa001"]*count, "time": epochs,
            "lastposupdate": [float(t) for t in epochs], "lat": [50.03]*count,
            "lon": [8.57]*count, "onground": [True]*count,
        })

    @staticmethod
    def synthetic_geometry(points):
        count = len(points)
        return np.zeros((count, 1)), np.zeros(count), np.full(count, 500.), np.zeros(count, bool)

    def run_silver(self, name, date_args):
        output = self.workspace / name
        argv = ["silver_m1.py", "--bronze-root", str(self.bronze),
                "--geometry-dir", str(self.geometry), "--output", str(output), *date_args]
        with patch("sys.argv", argv), patch.object(
                silver_m1, "load_geometry", return_value=(self.synthetic_geometry, ["synthetic"], {})):
            silver_m1.main()
        return output

    def test_date_and_date_list_reproduce_across_midnight_without_importing_next_cohort(self):
        self.flights(MIDNIGHT-86400, MIDNIGHT-10, "aaa001")
        self.flights(MIDNIGHT, MIDNIGHT+40, "aaa002")
        self.state(MIDNIGHT-3600, [MIDNIGHT-12, MIDNIGHT-1])
        self.state(MIDNIGHT, [MIDNIGHT, MIDNIGHT+8])
        date_list = self.workspace / "dates.txt"
        date_list.write_text(f"# One selected UTC date\n{DAY}\n{DAY}\n")
        first = self.run_silver("by-date", ["--date", DAY])
        repeat = self.run_silver("by-list", ["--date-list", str(date_list)])

        manifest = json.loads((first / "run_manifest.json").read_text())
        self.assertEqual(manifest["dates_utc"], [DAY])
        records = manifest["bronze_manifests"]
        self.assertIn("metadata/manifests/hours/dt=2030-01-01/hour-23.json", records)
        self.assertIn("metadata/manifests/hours/dt=2030-01-02/hour-00.json", records)
        self.assertNotIn("metadata/manifests/days/dt=2030-01-02/flights.json", records)
        arrivals = pq.read_table(first / "arrival_coverage.parquet").to_pylist()
        self.assertEqual([(row["icao24"], row["surface_points"]) for row in arrivals], [("aaa001", 4)])
        points = pq.read_table(first / "surface_points.parquet")
        self.assertEqual(points["position_epoch_s"].to_pylist(),
                         [MIDNIGHT-12, MIDNIGHT-1, MIDNIGHT, MIDNIGHT+8])
        self.assertEqual(points["fragment_no"].to_pylist(), [1, 1, 1, 1])
        for name in silver_m1.SCHEMAS:
            file = name + ".parquet"
            self.assertEqual((first / file).read_bytes(), (repeat / file).read_bytes())

    def test_missing_next_utc_hour_is_recorded_in_coverage(self):
        self.flights(MIDNIGHT-86400, MIDNIGHT-10, "aaa001")
        self.state(MIDNIGHT-3600, [MIDNIGHT-12, MIDNIGHT-1])
        output = self.run_silver("missing-next-hour", ["--date", DAY])
        records = json.loads((output / "run_manifest.json").read_text())["bronze_manifests"]
        self.assertEqual(records["metadata/manifests/hours/dt=2030-01-02/hour-00.json"]["status"],
                         "missing_manifest")
        coverage = pq.read_table(output / "arrival_coverage.parquet").to_pylist()[0]
        self.assertEqual(coverage["missing_or_noncomplete_source_hours"], 1)
        self.assertEqual(coverage["surface_points"], 2)


class OccupancyEvidenceTests(unittest.TestCase):
    def result(self, departure_fields, issues=()):
        arrivals = pd.DataFrame([{
            "day": DAY, "direction": "25L", "hold_lo": MIDNIGHT-2, "hold_hi": MIDNIGHT+2,
            "both_arrival_events": True,
        }])
        departure = {
            "day": DAY, "anchor": MIDNIGHT+20, "dep_runway": "25C",
            "dep_entry_lo": MIDNIGHT-20, "dep_first_inside_t": MIDNIGHT-10,
            "dep_last_inside_t": MIDNIGHT+12, "dep_end_hi": MIDNIGHT+18,
        }
        departures = pd.DataFrame([departure | d for d in departure_fields],
                                  columns=list(departure))
        apply_occupancy_alignment(arrivals, departures, issues)
        return arrivals.iloc[0]

    def test_full_observed_occupancy_spans_utc_midnight(self):
        row = self.result([{}])
        self.assertEqual(row.occupancy_at_hold, "observed_departure_occupied")
        self.assertTrue(row.joint_occupied_observed)
        self.assertFalse(row.joint_unoccupied_confirmed)

    def test_overlap_only_with_uncertain_boundary_is_not_confirmed(self):
        row = self.result([{"dep_first_inside_t": MIDNIGHT+1}])
        self.assertEqual(row.occupancy_at_hold, "occupancy_boundary_uncertain")
        self.assertFalse(row.joint_occupied_observed)
        self.assertFalse(row.joint_unoccupied_confirmed)

    def test_no_observed_overlap_is_not_confirmed_vacancy(self):
        scenarios = [
            {"dep_runway": "18"},
            {"dep_first_inside_t": MIDNIGHT-18, "dep_last_inside_t": MIDNIGHT-10,
             "dep_end_hi": MIDNIGHT-6},
        ]
        for departure in scenarios:
            with self.subTest(departure=departure):
                row = self.result([departure])
                self.assertEqual(row.occupancy_at_hold, "no_observed_overlap_proxy")
                self.assertTrue(row.joint_source_only_including_no_overlap)
                self.assertFalse(row.joint_occupied_observed)
                self.assertFalse(row.joint_unoccupied_confirmed)

    def test_missing_departure_evidence_remains_unknown(self):
        scenarios = [
            ([], ()),
            ([{"dep_runway": "unknown"}], ()),
            ([dict.fromkeys(("dep_entry_lo", "dep_first_inside_t",
                             "dep_last_inside_t", "dep_end_hi"), np.nan)], ()),
            ([{"dep_runway": "18"}], ((MIDNIGHT, "missing_manifest"),)),
        ]
        for departures, issues in scenarios:
            with self.subTest(departures=departures, issues=issues):
                row = self.result(departures, issues)
                self.assertEqual(row.occupancy_at_hold, "insufficient_departure_coverage")
                self.assertFalse(row.joint_occupied_observed)
                self.assertFalse(row.joint_unoccupied_confirmed)


if __name__ == "__main__":
    unittest.main()
