"""Synthetic fixtures for the analytics views (03 M4)."""
import sys
import unittest
from unittest.mock import patch

import analytics_views

DAY = "2030-01-01"


class FakeAnalyticsOps:
    def __init__(self, project, dataset, region="europe-west3"):
        self.project, self.dataset, self.region = project, dataset, region
        self.statements = []
        self.results = []

    def sql(self, statement):
        self.statements.append(statement)
        results = self.results.pop(0)
        return results

    def read_view(self, name, where="TRUE"):
        self.statements.append(f"read {name} {where}")
        return self.results.pop(0)

    def record_cost(self):
        return [{"job_id": "j1", "bytes_processed": 1234, "slot_ms": 10}]


def make_ops():
    """A fixed-sample world matching expected_results.json."""
    ops = FakeAnalyticsOps("p", "aviation")
    ops.results.append([  # traffic rows
        {"release_id": "v002", "day_utc": DAY, "status": "labeled", "arrivals": 3},
        {"release_id": "v002", "day_utc": DAY, "status": "no_surface", "arrivals": 1},
    ])
    ops.results.append([  # hourly rows
        {"release_id": "v002", "day_utc": DAY, "hour_utc": 9, "arrivals": 3, "labeled_arrivals": 2},
        {"release_id": "v002", "day_utc": DAY, "hour_utc": 10, "arrivals": 1, "labeled_arrivals": 1},
    ])
    ops.results.append([  # surface rows
        {"release_id": "v002", "day_utc": DAY, "labeled_arrivals": 3, "taxi_in_min_avg": 6.0,
         "taxi_in_min_median": 6.0, "taxi_in_min_min": 6.0, "taxi_in_min_max": 6.0,
         "taxi_path_m_avg": 800.0, "with_gap_over_30s": 1},
    ])
    return ops


EXPECTED = {
    "fixed_release_id": "v002",
    "v_arrival_traffic": [{"status": "labeled", "arrivals": 3},
                          {"status": "no_surface", "arrivals": 1}],
    "v_arrival_hourly": [{"day_utc": DAY, "arrivals": 4, "labeled": 3}],
    "v_surface_time": {"labeled_total": 3, "days": 1, "taxi_in_max_s": 2700},
}


class AnalyticsVerifyTests(unittest.TestCase):
    def test_expected_results_pass(self):
        ops = make_ops()
        results = analytics_views.verify(ops, EXPECTED)
        self.assertTrue(all(r["passed"] for r in results), results)

    def test_tampered_traffic_fails(self):
        ops = make_ops()
        ops.results[0][0]["arrivals"] = 99
        results = analytics_views.verify(ops, EXPECTED)
        self.assertFalse(all(r["passed"] for r in results))
        self.assertIn("traffic.labeled", [r["check"] for r in results if not r["passed"]])

    def test_tampered_daily_fails(self):
        ops = make_ops()
        ops.results[1][0]["arrivals"] = 5
        results = analytics_views.verify(ops, EXPECTED)
        self.assertFalse(all(r["passed"] for r in results))

    def test_out_of_contract_taxi_in_fails(self):
        ops = make_ops()
        ops.results[2][0]["taxi_in_min_max"] = 100.0  # 6000 s > 2700 s cap
        results = analytics_views.verify(ops, EXPECTED)
        self.assertIn("surface.taxi_in_max_within_contract",
                      [r["check"] for r in results if not r["passed"]])

    def test_view_sql_covers_documented_views(self):
        self.assertEqual(set(analytics_views.VIEWS),
                         {"v_arrival_traffic", "v_arrival_hourly", "v_surface_time"})


if __name__ == "__main__":
    unittest.main()
