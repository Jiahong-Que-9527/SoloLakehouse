"""Bronze-layer data quality checks."""

from __future__ import annotations

import datetime as dt

import pandas as pd


def check_no_nulls(df: pd.DataFrame, columns: list[str]) -> None:
    """Raise if any of the specified columns contain nulls."""
    missing_columns = [column for column in columns if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns for null check: {missing_columns}")

    null_counts = df[columns].isnull().sum()
    failing = null_counts[null_counts > 0]
    if not failing.empty:
        raise ValueError(f"Null values found: {failing.to_dict()}")


def check_date_range(df: pd.DataFrame, date_col: str, min_date: str, max_date: str) -> None:
    """Raise if dates fall outside [min_date, max_date]."""
    if date_col not in df.columns:
        raise ValueError(f"Missing date column: {date_col}")

    dates = pd.to_datetime(df[date_col], errors="coerce").dt.date
    if dates.isnull().any():
        raise ValueError(f"Invalid date values in column: {date_col}")

    min_allowed = dt.date.fromisoformat(min_date)
    max_allowed = dt.date.fromisoformat(max_date)
    out_of_range = dates[(dates < min_allowed) | (dates > max_allowed)]
    if not out_of_range.empty:
        raise ValueError(
            f"Dates out of range [{min_allowed.isoformat()}, {max_allowed.isoformat()}] "
            f"in column {date_col}"
        )


def check_no_future_dates(df: pd.DataFrame, date_col: str) -> None:
    """Raise if any date in date_col is later than datetime.date.today()."""
    if date_col not in df.columns:
        raise ValueError(f"Missing date column: {date_col}")

    dates = pd.to_datetime(df[date_col], errors="coerce").dt.date
    if dates.isnull().any():
        raise ValueError(f"Invalid date values in column: {date_col}")

    today = dt.date.today()
    if (dates > today).any():
        raise ValueError(f"Future dates found in {date_col}")


def check_date_continuity(df: pd.DataFrame, date_col: str, max_gap_days: int) -> None:
    """Raise if any gap between consecutive dates exceeds max_gap_days."""
    if date_col not in df.columns:
        raise ValueError(f"Missing date column: {date_col}")

    dates = pd.to_datetime(df[date_col], errors="coerce").dropna().sort_values()
    if dates.empty:
        raise ValueError(f"No valid dates found in column: {date_col}")

    deltas = dates.diff().dropna().dt.days
    if not deltas.empty and int(deltas.max()) > max_gap_days:
        raise ValueError(f"Date gap exceeds {max_gap_days} days in {date_col}")


def check_schema_version(df: pd.DataFrame, expected_columns: list[str]) -> None:
    """Raise if df is missing any column from expected_columns."""
    missing_columns = [column for column in expected_columns if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing expected columns: {missing_columns}")


def run_ecb_bronze_checks(df: pd.DataFrame) -> None:
    """Run ECB-specific bronze checks."""
    expected_columns = [
        "observation_date",
        "rate_pct",
        "_ingestion_timestamp",
        "_source",
    ]
    check_no_nulls(df, ["observation_date", "rate_pct"])
    check_no_future_dates(df, "observation_date")
    check_date_continuity(df, "observation_date", max_gap_days=180)
    check_schema_version(df, expected_columns)


def run_dax_bronze_checks(df: pd.DataFrame) -> None:
    """Run DAX-specific bronze checks."""
    expected_columns = [
        "observation_date",
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "volume",
        "_ingestion_timestamp",
        "_source",
    ]
    check_no_nulls(df, ["open_price", "high_price", "low_price", "close_price", "volume"])
    check_no_future_dates(df, "observation_date")
    check_date_continuity(df, "observation_date", max_gap_days=5)
    check_schema_version(df, expected_columns)
