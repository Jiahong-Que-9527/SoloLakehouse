"""Synthetic fixtures for the monthly Silver merge (02 M4)."""
import contextlib
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq

import merge_silver_month
import silver_v2

SCHEMAS = {t: pa.schema([f for f in silver_v2.SCHEMAS[t]])
           for t in merge_silver_month.TABLES}
DAYS = ("2024-11-01", "2024-11-02")


@contextlib.contextmanager
def patch_argv(*argv):
    with patch.object(sys, "argv", ["merge_silver_month.py", *argv]):
        yield


class MergeMonthTests(unittest.TestCase):
    def setUp(self):
        self.workspace = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="merge-month-")))
        self.daily = self.workspace / "daily"
        self.daily.mkdir()
        for day in DAYS:
            out = self.daily / day
            out.mkdir()
            (out / "run_manifest.json").write_text(json.dumps({"dates_utc": [day]}))
            for table, schema in SCHEMAS.items():
                pq.write_table(pa.table({f.name: pa.array([], type=f.type)
                                         for f in schema}), out / f"{table}.parquet")
            # One observation row per day so the merge proves concatenation.
            row = {f.name: (date.fromisoformat(day) if f.name == "day_utc" else
                            "aaa" if f.name == "icao24" else None)
                   for f in SCHEMAS["observations"]}
            table = pq.read_table(out / "observations.parquet")
            pq.write_table(pa.concat_tables(
                [table, pa.Table.from_pylist([row], schema=SCHEMAS["observations"])]),
                out / "observations.parquet")

    def run_merge(self, month="2024-11", out=None):
        out = out or (self.workspace / "monthly")
        with patch_argv("--daily-root", str(self.daily), "--month", month,
                        "--output", str(out)):
            merge_silver_month.main()
        return out

    def test_merge_concatenates_daily_files(self):
        out = self.run_merge()
        merged = pq.read_table(out / "observations.parquet")
        days = sorted({str(d) for d in merged.column("day_utc").to_pylist()})
        self.assertEqual(days, list(DAYS))
        for table in merge_silver_month.TABLES:
            self.assertTrue((out / f"{table}.parquet").is_file(), table)
        manifest = json.loads((out / "run_manifest.json").read_text())
        self.assertEqual(manifest["dates_utc"], list(DAYS))
        self.assertEqual(len(manifest["missing_dates_utc"]), 28)
        self.assertEqual(manifest["missing_dates_utc"][0], "2024-11-03")

    def test_month_days_covers_leap_and_year_end(self):
        self.assertEqual(merge_silver_month.month_days("2024-02")[1], "2024-02-02")
        self.assertEqual(len(merge_silver_month.month_days("2024-02")), 29)
        self.assertEqual(merge_silver_month.month_days("2024-12")[-1], "2024-12-31")

    def test_incomplete_day_is_omitted_from_every_table(self):
        (self.daily / DAYS[0] / "segments.parquet").unlink()
        out = self.run_merge()
        manifest = json.loads((out / "run_manifest.json").read_text())
        self.assertEqual(manifest["dates_utc"], [DAYS[1]])
        self.assertIn(DAYS[0], manifest["missing_dates_utc"])
        dates = pq.read_table(out / "observations.parquet")["day_utc"].to_pylist()
        self.assertEqual(dates, [date.fromisoformat(DAYS[1])])

    def test_empty_month_records_all_dates(self):
        out = self.run_merge("2024-12")
        self.assertEqual(sorted(p.name for p in out.iterdir()), ["run_manifest.json"])
        manifest = json.loads((out / "run_manifest.json").read_text())
        self.assertEqual(manifest["dates_utc"], [])
        self.assertEqual(manifest["missing_dates_utc"], merge_silver_month.month_days("2024-12"))


if __name__ == "__main__":
    unittest.main()
