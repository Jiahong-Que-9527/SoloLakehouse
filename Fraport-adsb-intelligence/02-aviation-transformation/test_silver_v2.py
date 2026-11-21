"""Synthetic Bronze fixtures for the neutral Silver v2 build (ADR-006)."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq

import silver_v2

DAY = "2030-01-01"
DAY_STAMP = int(datetime(2030, 1, 1, tzinfo=timezone.utc).timestamp())


class SilverV2Tests(unittest.TestCase):
    def setUp(self):
        self.workspace = Path(tempfile.mkdtemp(prefix="silver-v2-synthetic-"))
        self.bronze = self.workspace / "bronze"
        self.output = self.workspace / "out"

    def partition(self, kind, hour, contents, status="complete"):
        timestamp = datetime.fromtimestamp(hour, timezone.utc)
        day = timestamp.date().isoformat()
        if kind == "states":
            prefix, name, dataset = "hours", f"hour-{timestamp:%H}", "eddf_r75km"
            window = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            prefix, name, dataset = "days", "flights", "eddf_flights"
            window = f"{day}T00:00:00Z"
        data = self.bronze / "fixtures" / f"dt={day}" / f"{name}.parquet"
        data.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.table(contents), data)
        manifest = self.bronze / "metadata/manifests" / prefix / f"dt={day}" / f"{name}.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({
            "dataset_id": dataset, "dataset_version": "v1", "status": status,
            "window_start": window,
            "path": str(data.relative_to(self.bronze)), "sha256": silver_v2.digest(data),
        }))

    def states(self, hour, rows):
        count = len(rows["icao24"])
        full = {k: rows.get(k, [None] * count) for k in
                ("icao24", "time", "lastposupdate", "lat", "lon", "velocity",
                 "heading", "vertrate", "callsign", "onground", "baroaltitude",
                 "geoaltitude")}
        self.partition("states", hour, full)

    def build_bronze(self):
        t = DAY_STAMP
        # hour-00: aaa001 segment 1 (t+10..30, with an exact duplicate), a stale
        # state (age 20 s), segment 2 after a 45 s gap (t+75..80); ccc003 with an
        # implausible displacement; bbb002 near the hour boundary.
        self.states(t, {
            "icao24": ["aaa001"] * 7 + ["ccc003"] * 2 + ["bbb002"] + ["filler0"],
            "time": [t+10, t+20, t+30, t+30, t+75, t+80, t+22,
                     t+100, t+101, t+3550, t+1],
            "lastposupdate": [t+10, t+20, t+30, t+30, t+75, t+80, t+2,
                              t+100, t+101, t+3550, t+1],
            "lat": [50.0] * 11,
            "lon": [8.5] * 8 + [8.505] + [8.5] * 2,
            "onground": [False, False, False, False, True, True, False,
                         True, True, False, False],
        })
        # hour-01: bbb002 continues after a 100 s gap across the hour boundary.
        self.states(t + 3600, {
            "icao24": ["bbb002", "filler1"],
            "time": [t+3650, t+3610],
            "lastposupdate": [t+3650, t+3610],
            "lat": [50.0, 50.0], "lon": [8.5, 8.5], "onground": [False, False],
        })
        # hour-02 exists but is not complete: its states must never be read.
        self.partition("states", t + 7200, {
            "icao24": ["ghost"], "time": [t+7300], "lastposupdate": [t+7300],
            "lat": [50.0], "lon": [8.5], "onground": [False],
        }, status="source_gap")
        # flights: one duplicate pair + one other aircraft.
        self.partition("flights", t, {
            "icao24": ["AAA001", "AAA001", "bbb002"],
            "callsign": ["DLH1AB", "DLH1AB", "DLH2CD"],
            "firstseen": [t+5, t+5, t+3400], "lastseen": [t+90, t+90, t+3520],
            "estdepartureairport": ["EDDF", "EDDF", "EDDF"],
            "estarrivalairport": ["EDDM", "EDDM", "EDDF"],
        })

    def run_main(self):
        with patch.object(sys, "argv", ["silver_v2.py", "--bronze-root", str(self.bronze),
                                        "--date", DAY, "--output", str(self.output)]):
            silver_v2.main()

    def read(self, name):
        return pq.read_table(self.output / f"{name}.parquet").to_pylist()

    def test_neutral_layer_tables(self):
        self.build_bronze()
        self.run_main()

        observations = self.read("observations")
        self.assertFalse(any("onground" in o for o in observations))
        aaa = [o for o in observations if o["icao24"] == "aaa001"]
        self.assertEqual([o["time_epoch_s"] for o in aaa], [DAY_STAMP+10, DAY_STAMP+20, DAY_STAMP+30, DAY_STAMP+75, DAY_STAMP+80])
        self.assertTrue(any(o["onground_raw"] for o in aaa))
        self.assertTrue(any(not o["onground_raw"] for o in aaa))

        segments = {s["icao24"]: [x for x in self.read("segments") if x["icao24"] == s["icao24"]]
                    for s in self.read("segments")}
        aaa_segments = segments["aaa001"]
        self.assertEqual(len(aaa_segments), 2)
        self.assertEqual(aaa_segments[0]["break_reason_after"], "time_gap")
        self.assertEqual(aaa_segments[0]["gap_after_s"], 45)
        self.assertFalse(aaa_segments[-1]["ends_before_break"])

        self.assertEqual(segments["ccc003"][0]["break_reason_after"], "implausible_displacement")
        self.assertEqual(segments["bbb002"][0]["break_reason_after"], "time_gap")

        flights = self.read("flights")
        self.assertEqual(len(flights), 2)

        coverage = {c["icao24"]: c for c in self.read("daily_coverage")}
        self.assertEqual(coverage["aaa001"]["observation_count"], 5)
        self.assertEqual(coverage["aaa001"]["stale_dropped"], 1)
        self.assertEqual(coverage["aaa001"]["duplicates_dropped"], 1)
        self.assertEqual(coverage["aaa001"]["flights_recorded"], 1)
        self.assertNotIn("ghost", coverage)

        manifest = json.loads((self.output / "run_manifest.json").read_text())
        self.assertEqual(manifest["schema_version"], "silver-eddf-v2")
        self.assertEqual(manifest["policy"]["onground_flag"], "carried_raw_never_used")
        unavailable = manifest["unavailable_hours"][DAY]
        self.assertIn(DAY_STAMP+7200, [h for h, _ in unavailable])
        self.assertNotIn("ghost", coverage)

    def test_source_partition_reason_is_unit_level(self):
        # A break can only cite a source partition when the unavailable hour's
        # window is crossed between two readable states.
        points = [dict(time_epoch_s=DAY_STAMP+3590, lat=50.0, lon=8.5),
                  dict(time_epoch_s=DAY_STAMP+3605, lat=50.0, lon=8.5)]
        observation_rows, segment_rows, _ = silver_v2.segment_aircraft(
            datetime.fromisoformat(DAY).date(), "ddd004", self.raw_rows(points),
            [(DAY_STAMP+3600, "source_gap")],
        )
        self.assertEqual(len(segment_rows), 2)
        self.assertEqual(segment_rows[0]["break_reason_after"], "source_partition")

    @staticmethod
    def raw_rows(points):
        return [("ddd004", p["time_epoch_s"], p["time_epoch_s"], p["lat"], p["lon"],
                 None, None, None, None, None, False, None) for p in points]

    def test_output_guardrails(self):
        self.build_bronze()
        existing = self.workspace / "existing"
        existing.mkdir()
        with patch.object(sys, "argv", ["silver_v2.py", "--bronze-root", str(self.bronze),
                                        "--date", DAY, "--output", str(existing)]):
            with self.assertRaises(SystemExit):
                silver_v2.main()


if __name__ == "__main__":
    unittest.main()
