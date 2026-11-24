"""Regression tests for chronological tuning and feature isolation."""

import unittest
from unittest.mock import patch

import numpy as np

from boosted_candidate import FEATURES, fit_candidate, selected_features, split_rows


def observation(at, status="matched_labeled"):
    return {"prediction_at": at, "trigger_event_at": at - 5, "match_status": status}


class CandidateTests(unittest.TestCase):
    def test_time_splits_apply_the_label_embargo_at_both_cutoffs(self):
        rows = [observation(at) for at in (1000, 5000, 8999, 9000, 13000, 14000)]
        rows.append(observation(15000, "unmatched"))
        self.assertEqual(split_rows(rows, 9000, 14000, 90), {
            "tune_train": [0, 1], "validation": [3], "train": [0, 1, 2, 3], "holdout": [5],
        })

    def test_manifest_cannot_add_a_label_or_identifier_as_a_predictor(self):
        for forbidden in ("taxi_in_s", "label_flight_key", "prediction_id"):
            with self.subTest(forbidden=forbidden), self.assertRaisesRegex(ValueError, "approved"):
                selected_features({"training_features": [*FEATURES, forbidden]})

    def test_holdout_values_are_never_read_by_search_or_final_fit(self):
        values = np.arange(20, dtype=float).reshape(10, 2)
        labels = np.arange(10, dtype=float)
        split = {"tune_train": [0, 1, 2, 3], "validation": [4, 5],
                 "train": [0, 1, 2, 3, 4, 5], "holdout": [6, 7, 8, 9]}

        class Estimator:
            def __init__(self, **params):
                self.offset = params["max_leaf_nodes"]

            def fit(self, features, targets):
                assert np.max(features) < 12
                assert np.max(targets) < 6

            def predict(self, features):
                assert np.max(features) < 12
                return np.full(len(features), self.offset, dtype=float)

        with patch("boosted_candidate.HistGradientBoostingRegressor", Estimator):
            _, best, _ = fit_candidate(values, labels, split)
            values[6:] = 1000
            labels[6:] = 999
            _, repeated, _ = fit_candidate(values, labels, split)
        self.assertEqual(best, repeated)
