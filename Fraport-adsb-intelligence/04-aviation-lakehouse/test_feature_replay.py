"""Exercise cutoff, duplicate handling, UTC boundaries and offline matching."""

import unittest
from datetime import date

import duckdb
import pyarrow as pa

from feature_replay import FEATURES, epoch, replay, summarize


class ReplayTests(unittest.TestCase):
    start = date(2024, 11, 1)
    end = date(2024, 12, 1)

    def observe(self, icao, at, available, ground, speed):
        start = epoch(self.start)
        return {"icao24": icao, "time_epoch_s": start + at,
                "available_at_epoch_s": start + available, "onground_raw": ground,
                "velocity_mps": speed, "geoaltitude_m": 100.0, "vertrate_mps": -3.0,
                "airport_ref_distance_m": 1000.0}

    def outcome(self, icao, surface, end):
        start = epoch(self.start)
        return {"icao24": icao, "day_utc": self.start, "flight_key": f"{icao}:retrospective",
                "status": "labeled", "taxi_in_s": end - surface,
                "surface_start_epoch_s": start + surface, "taxi_end_epoch_s": start + end}

    def run_replay(self, observations, outcomes, delay=None):
        with duckdb.connect() as connection:
            connection.register("silver_observations", pa.Table.from_pylist(observations))
            connection.register("outcomes", pa.Table.from_pylist(outcomes))
            return replay(connection, self.start, self.end, delay)

    def test_late_observation_cannot_replace_the_visible_boundary_approach(self):
        prior = self.observe("aaaaaa", -10, -9, False, 100.0)
        observations = [
            prior, dict(prior), self.observe("aaaaaa", -1, 30, False, 900.0),
            self.observe("aaaaaa", 3, 4, True, 20.0),
            self.observe("bbbbbb", 5, 6, False, 99.0), self.observe("bbbbbb", 7, 8, True, 21.0),
            self.observe("cccccc", 44, 48, False, 110.0), self.observe("cccccc", 50, 70, True, 24.0),
        ]
        labels = [self.outcome("aaaaaa", 3, 200), self.outcome("cccccc", 50, 65)]
        result = self.run_replay(observations, labels)
        first, unmatched, ended = result.to_pylist()
        self.assertEqual(first["approach_speed_mps"], 100.0)
        self.assertEqual(first["prior_event_at"], epoch(self.start) - 10)
        self.assertEqual(first["taxi_in_s"], 197)
        self.assertEqual(unmatched["match_status"], "unmatched")
        self.assertEqual(ended["match_status"], "already_ended")
        self.assertIsNone(ended["taxi_in_s"])
        self.assertEqual(summarize(result)["training_label_coverage"], 1 / 3)
        self.assertNotIn("label_flight_key", FEATURES)
        self.assertNotIn("taxi_in_s", FEATURES)

    def test_simulated_delay_sets_cutoff_and_does_not_use_observed_column(self):
        observations = [self.observe("aaaaaa", 10, 100, False, 100.0),
                        self.observe("aaaaaa", 12, 99, True, 20.0)]
        outcomes = [self.outcome("aaaaaa", 12, 200)]
        self.assertEqual(len(self.run_replay(observations, outcomes)), 0)
        simulated = self.run_replay(observations, outcomes, delay=5)
        self.assertEqual(simulated["prediction_at"].to_pylist(), [epoch(self.start) + 17])

    def test_missing_availability_rejected_in_observed_replay(self):
        observation = self.observe("aaaaaa", 5, 6, False, 100.0)
        observation["available_at_epoch_s"] = None
        with self.assertRaisesRegex(ValueError, "missing or invalid observation availability"):
            self.run_replay([observation], [self.outcome("aaaaaa", 5, 200)])
