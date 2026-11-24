import unittest

from seasonal_evaluation import score, traffic_groups


class SeasonalEvaluationTests(unittest.TestCase):
    def test_traffic_uses_the_previous_available_hour_and_excludes_same_second(self):
        seconds = [3600, 7200, 0, *range(1, 10), 3600]
        groups = traffic_groups(seconds, month_start=0)
        self.assertEqual(groups[:3], ["10–19", "0–9", "insufficient history"])
        self.assertEqual(groups[-1], groups[0])
        self.assertEqual(traffic_groups([3600], month_start=5), ["insufficient history"])

    def test_both_models_score_the_same_labels_and_coverage_counts_all_rows(self):
        result = score([(120.0, 110), (200.0, 195), (400.0, None)], 150)
        self.assertEqual(result["predictions"], 3)
        self.assertEqual(result["evaluated_labels"], 2)
        self.assertEqual(result["label_coverage"], 2 / 3)
        self.assertEqual(result["candidate_metrics_seconds"]["mae"], 7.5)
        self.assertEqual(result["baseline_metrics_seconds"]["mae"], 42.5)
        self.assertEqual(result["mae_improvement_seconds"], 35)

    def test_unlabeled_and_empty_groups_do_not_claim_a_score(self):
        self.assertEqual(score([(100.0, None)], 150)["label_coverage"], 0)
        self.assertIsNone(score([(100.0, None)], 150)["mae_improvement_seconds"])
        self.assertIsNone(score([], 150)["label_coverage"])


if __name__ == "__main__":
    unittest.main()
