from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from ingestion.quality.bronze_checks import (
    check_date_continuity,
    check_no_future_dates,
    check_no_nulls,
    check_schema_version,
    run_dax_bronze_checks,
    run_ecb_bronze_checks,
)


def _base_ecb_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "observation_date": ["2024-01-01", "2024-03-01", "2024-06-01"],
            "rate_pct": [4.0, 4.25, 4.5],
            "_ingestion_timestamp": [dt.datetime.now(dt.timezone.utc)] * 3,
            "_source": ["ECB_SDW"] * 3,
        }
    )


def _base_dax_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "observation_date": ["2024-01-02", "2024-01-03", "2024-01-05"],
            "open_price": [100.0, 101.0, 102.0],
            "high_price": [101.0, 102.0, 103.0],
            "low_price": [99.0, 100.0, 101.0],
            "close_price": [100.5, 101.5, 102.5],
            "volume": [1000.0, 2000.0, 3000.0],
            "_ingestion_timestamp": [dt.datetime.now(dt.timezone.utc)] * 3,
            "_source": ["DAX_SAMPLE"] * 3,
        }
    )


class TestQualityChecks:
    def test_check_no_future_dates_pass(self) -> None:
        df = pd.DataFrame({"observation_date": ["2024-01-01"]})
        check_no_future_dates(df, "observation_date")

    def test_check_no_future_dates_fail(self) -> None:
        tomorrow = dt.date.today() + dt.timedelta(days=1)
        df = pd.DataFrame({"observation_date": [tomorrow.isoformat()]})
        with pytest.raises(ValueError, match="Future dates"):
            check_no_future_dates(df, "observation_date")

    def test_check_date_continuity_pass(self) -> None:
        df = pd.DataFrame({"observation_date": ["2024-01-01", "2024-01-04", "2024-01-07"]})
        check_date_continuity(df, "observation_date", max_gap_days=3)

    def test_check_date_continuity_fail(self) -> None:
        df = pd.DataFrame({"observation_date": ["2024-01-01", "2024-07-19"]})
        with pytest.raises(ValueError, match="Date gap exceeds 180 days"):
            check_date_continuity(df, "observation_date", max_gap_days=180)

    def test_check_schema_version_pass(self) -> None:
        df = pd.DataFrame({"a": [1], "b": [2]})
        check_schema_version(df, ["a", "b"])

    def test_check_schema_version_fail(self) -> None:
        df = pd.DataFrame({"a": [1]})
        with pytest.raises(ValueError, match="Missing expected columns"):
            check_schema_version(df, ["a", "b"])

    def test_check_no_nulls_pass(self) -> None:
        df = pd.DataFrame({"a": [1], "b": [2]})
        check_no_nulls(df, ["a", "b"])

    def test_check_no_nulls_fail(self) -> None:
        df = pd.DataFrame({"a": [1], "b": [None]})
        with pytest.raises(ValueError, match="Null values found"):
            check_no_nulls(df, ["a", "b"])

    def test_run_ecb_bronze_checks_pass(self) -> None:
        run_ecb_bronze_checks(_base_ecb_df())

    def test_run_ecb_bronze_checks_fail(self) -> None:
        failing = _base_ecb_df().drop(columns=["_source"])
        with pytest.raises(ValueError, match="Missing expected columns"):
            run_ecb_bronze_checks(failing)

    def test_run_dax_bronze_checks_pass(self) -> None:
        run_dax_bronze_checks(_base_dax_df())

    def test_run_dax_bronze_checks_fail(self) -> None:
        failing = _base_dax_df().copy()
        failing.loc[1, "observation_date"] = (dt.date.today() + dt.timedelta(days=1)).isoformat()
        with pytest.raises(ValueError, match="Future dates"):
            run_dax_bronze_checks(failing)
