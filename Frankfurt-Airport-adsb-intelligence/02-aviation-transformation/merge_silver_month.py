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
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

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


def daily_input(root: Path, day: str, tables: tuple[str, ...]) -> str | None:
    """Return the completion manifest's digest when all required files exist."""
    folder = root / day
    manifest = folder / "run_manifest.json"
    if not manifest.is_file() or any(
        not (folder / f"{table}.parquet").is_file() for table in tables
    ):
        return None
    contents = manifest.read_bytes()
    recorded = json.loads(contents)
    if recorded["dates_utc"] != [day]:
        raise ValueError(f"{manifest}: expected Silver for {day}")
    return hashlib.sha256(contents).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--daily-root", type=Path, required=True)
    parser.add_argument("--month", required=True, help="YYYY-MM")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    days = month_days(args.month)
    inputs = {day: sha for day in days
              if (sha := daily_input(args.daily_root, day, TABLES)) is not None}
    missing = [day for day in days if day not in inputs]
    if missing:
        print(f"missing Silver days ({len(missing)}): {', '.join(missing)}")
    manifest = {
        "schema_version": "silver-month-v1",
        "requested_dates_utc": days,
        "dates_utc": list(inputs),
        "missing_dates_utc": missing,
        "daily_manifest_sha256": inputs,
    }
    if args.output.exists():
        parser.error("output directory already exists")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".silver-month-", dir=args.output.parent) as temp:
        staging = Path(temp) / "month"
        staging.mkdir(mode=0o700)
        if inputs:
            with duckdb.connect() as con:
                con.execute("set threads=4")
                for table in TABLES:
                    files = [str(args.daily_root / day / f"{table}.parquet")
                             for day in inputs]
                    con.from_parquet(files).write_parquet(
                        str(staging / f"{table}.parquet"),
                        compression="zstd", row_group_size=65536)
                    print(f"{table}: {len(files)} daily files merged")
        (staging / "run_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        staging.rename(args.output)


if __name__ == "__main__":
    main()
