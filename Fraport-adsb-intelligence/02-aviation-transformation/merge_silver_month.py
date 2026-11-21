"""Merge daily Silver outputs into one monthly Silver root (02 M4).

DuckDB streams the copy, so a month of ~90M observations never sits in
Python memory. The monthly root keeps the flat layout gold_ground_ops
expects: observations.parquet, segments.parquet, flights.parquet,
daily_coverage.parquet.

    uv run --locked python merge_silver_month.py \
      --daily-root /path/full/silver --month 2024-11 \
      --output /path/full/silver-monthly/2024-11
"""
import argparse
from datetime import date, timedelta
from pathlib import Path

import duckdb

TABLES = ("observations", "segments", "flights", "daily_coverage")


def month_days(month: str) -> list[str]:
    year, mon = int(month[:4]), int(month[5:7])
    first, last = date(year, mon, 1), date(year + mon // 12, mon % 12 + 1, 1)
    days = []
    while first < last:
        days.append(first.isoformat())
        first += timedelta(days=1)
    return days


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--daily-root", type=Path, required=True)
    parser.add_argument("--month", required=True, help="YYYY-MM")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    days = month_days(args.month)
    con = duckdb.connect()
    con.execute("set threads=4")
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    for table in TABLES:
        files = [str(args.daily_root / d / f"{table}.parquet") for d in days
                 if (args.daily_root / d / f"{table}.parquet").is_file()]
        if not files:
            raise SystemExit(f"no {table}.parquet under {args.daily_root} for {args.month}")
        con.execute(
            f"COPY (SELECT * FROM read_parquet({files!r})) "
            f"TO '{args.output / f'{table}.parquet'}' "
            f"(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 65536)")
        print(f"{table}: {len(files)} daily files merged")


if __name__ == "__main__":
    main()
