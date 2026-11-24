"""Check the month boundary, consistent feature rules and frozen scoring coverage."""

import unittest
from datetime import UTC, datetime

import numpy as np

from frozen_evaluation import comparison, validate_evaluation


def manifest(month):
    return {"label_release": {"release_id": f"geometry-v2-{month}"},
            "training_features": ["example"], "availability": {"delay_seconds": 5},
            "rules": {"match_window_s": 90}, "code_sha256": {"feature_replay.py": "example"}}


def row(day, label):
    event = int(datetime.fromisoformat(day).replace(tzinfo=UTC).timestamp())
    return {"trigger_event_at": event, "prediction_at": event + 5, "taxi_in_s": label,
            "match_status": "matched_labeled" if label is not None else "unmatched"}


class FrozenEvaluationTests(unittest.TestCase):
    def test_later_release_and_timestamp_required(self):
        training, evaluation = manifest("2024-11"), manifest("2024-12")
        case = [row("2024-12-01", 10)]
        validate_evaluation(training, evaluation, case)
        with self.assertRaisesRegex(ValueError, "must be later"):
            validate_evaluation(training, training, case)
        with self.assertRaisesRegex(ValueError, "outside its release month"):
            validate_evaluation(training, evaluation, [row("2024-11-30", 10)])

    def test_observation_availability_must_be_comparable(self):
        training, evaluation = manifest("2024-11"), manifest("2024-12")
        evaluation["availability"]["delay_seconds"] = 10
        with self.assertRaisesRegex(ValueError, "differ in availability"):
            validate_evaluation(training, evaluation, [row("2024-12-01", 10)])

    def test_both_models_use_same_labels_and_coverage_counts_every_prediction(self):
        rows = [row("2024-12-01", 100), row("2024-12-01", None), row("2024-12-02", 300),
                row("2024-12-03", None)]
        result = comparison(rows, np.array([130, 999, 250, 999]), baseline_seconds=200)
        self.assertEqual(result["label_coverage"], .5)
        self.assertEqual(result["candidate_metrics_seconds"]["mae"], 40)
        self.assertEqual(result["baseline_metrics_seconds"]["mae"], 100)
        self.assertEqual(result["mae_improvement_seconds"], 60)
        self.assertIsNone(result["daily"][2]["candidate_mae_seconds"])
