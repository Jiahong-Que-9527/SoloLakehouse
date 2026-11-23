import unittest
from unittest.mock import patch

from cloud_analytics import MAX_BYTES_BILLED, reconcile_existing_release


class BigQueryReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.handoff = {"release_id": "geometry-v2-2024-12", "manifest_sha256": "a" * 64,
                        "rows": 16, "coverage_status_counts": {"labeled": 13}}
        self.entry = {"data_product": "ground-ops", "manifest_sha256": "a" * 64, "row_count": "16"}
        self.row = {"entries": [self.entry], "total_rows": "16", "labeled_rows": "13", "duplicate_keys": "0"}
        self.job = {"statistics": {"query": {"statementType": "SELECT", "totalBytesBilled": "0", "cacheHit": True}}}

    def test_existing_release_uses_only_a_capped_parameterized_select_and_job_lookup(self):
        with patch("cloud_analytics.bq_json", side_effect=[[self.row], self.job]) as bq:
            result = reconcile_existing_release("slh-gcp-test", self.handoff)
        self.assertEqual(result["status"], "already_ingested")
        self.assertEqual(result["rows_added"], 0)
        self.assertEqual(result["geometry_counts"], {"rows": 16, "labeled_rows": 13, "duplicate_keys": 0})
        (query, sql), (show,) = [call.args for call in bq.call_args_list]
        self.assertIn("query", query)
        self.assertIn(f"--maximum_bytes_billed={MAX_BYTES_BILLED}", query)
        self.assertIn("--parameter=release_id:STRING:geometry-v2-2024-12", query)
        self.assertIn("@release_id", sql)
        self.assertNotRegex(sql, r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|DROP|TRUNCATE)\b")
        self.assertEqual(show[-3:], ["show", "--job", f"slh-gcp-test:{result['job_id']}"])

    def test_absent_or_ambiguous_ledger_and_mismatches_fail_closed(self):
        for row in ({**self.row, "entries": None}, {**self.row, "entries": [self.entry, self.entry]},
                    {**self.row, "entries": [{**self.entry, "manifest_sha256": "b" * 64}]},
                    {**self.row, "duplicate_keys": "1"}):
            with self.subTest(row=row), patch("cloud_analytics.bq_json", return_value=[row]) as bq:
                with self.assertRaises(ValueError):
                    reconcile_existing_release("slh-gcp-test", self.handoff)
                bq.assert_called_once()

    def test_invalid_project_never_calls_bigquery(self):
        with patch("cloud_analytics.bq_json") as bq:
            with self.assertRaisesRegex(ValueError, "project ID"):
                reconcile_existing_release("slh-gcp-test`", self.handoff)
            bq.assert_not_called()
