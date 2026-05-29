from __future__ import annotations

import datetime as dt
import importlib
from unittest.mock import MagicMock

import pandas as pd

from transformations import dax_bronze_to_silver, ecb_bronze_to_silver, silver_to_gold_features


def _make_catalog() -> MagicMock:
    return MagicMock(name="catalog")


class TestTransformationRuns:
    def test_ecb_run_reads_bronze_and_writes_silver(self, monkeypatch) -> None:
        importlib.reload(ecb_bronze_to_silver)
        bronze = pd.DataFrame(
            {
                "observation_date": ["2024-01-01", "2024-01-02"],
                "rate_pct": [4.0, 4.25],
                "_ingestion_timestamp": [dt.datetime.now(dt.UTC)] * 2,
                "_source": ["ECB_SDW"] * 2,
            }
        )
        written: list[pd.DataFrame] = []

        monkeypatch.setattr(ecb_bronze_to_silver, "scan_table", lambda cat, ns, tbl: bronze)
        monkeypatch.setattr(
            ecb_bronze_to_silver,
            "overwrite_table",
            lambda cat, ns, tbl, df, schema, **_: written.append(df),
        )
        quality_calls: list[tuple[int, str]] = []
        monkeypatch.setattr(
            ecb_bronze_to_silver,
            "run_silver_quality_report",
            lambda df, layer: quality_calls.append((len(df), layer)),
        )

        result = ecb_bronze_to_silver.run(_make_catalog())

        assert result["table"] == "iceberg:silver.ecb_rates_cleaned"
        assert result["row_count"] == 2
        assert quality_calls == [(2, "ecb_rates_cleaned")]
        assert written[0].columns.tolist() == ["observation_date", "rate_pct", "rate_change_bps"]

    def test_dax_run_reads_bronze_and_writes_silver(self, monkeypatch) -> None:
        importlib.reload(dax_bronze_to_silver)
        bronze = pd.DataFrame(
            {
                "observation_date": ["2024-01-05", "2024-01-08"],
                "open_price": [100.0, 101.0],
                "high_price": [101.0, 102.0],
                "low_price": [99.0, 100.0],
                "close_price": [100.0, 102.0],
                "volume": [1000.0, 1100.0],
                "_ingestion_timestamp": [dt.datetime.now(dt.UTC)] * 2,
                "_source": ["DAX_SAMPLE"] * 2,
            }
        )
        written: list[pd.DataFrame] = []

        monkeypatch.setattr(dax_bronze_to_silver, "scan_table", lambda cat, ns, tbl: bronze)
        monkeypatch.setattr(
            dax_bronze_to_silver,
            "overwrite_table",
            lambda cat, ns, tbl, df, schema, **_: written.append(df),
        )
        quality_calls: list[tuple[int, str]] = []
        monkeypatch.setattr(
            dax_bronze_to_silver,
            "run_silver_quality_report",
            lambda df, layer: quality_calls.append((len(df), layer)),
        )

        result = dax_bronze_to_silver.run(_make_catalog())

        assert result["table"] == "iceberg:silver.dax_daily_cleaned"
        assert quality_calls == [(2, "dax_daily_cleaned")]
        assert "daily_return" in written[0].columns

    def test_gold_run_reads_silver_and_writes_gold(self, monkeypatch) -> None:
        importlib.reload(silver_to_gold_features)
        ecb = pd.DataFrame(
            {
                "observation_date": ["2024-01-10", "2024-01-11"],
                "rate_pct": [4.0, 4.25],
                "rate_change_bps": [0.0, 25.0],
            }
        )
        dax_dates = pd.date_range("2024-01-02", periods=20, freq="B")
        dax = pd.DataFrame(
            {
                "observation_date": dax_dates.date,
                "close_price": [100 + i for i in range(20)],
                "daily_return": [0.1 + i * 0.01 for i in range(20)],
            }
        )
        scan_returns = iter([ecb, dax])

        monkeypatch.setattr(
            silver_to_gold_features,
            "scan_table",
            lambda cat, ns, tbl: next(scan_returns),
        )
        written: list[pd.DataFrame] = []
        monkeypatch.setattr(
            silver_to_gold_features,
            "overwrite_table",
            lambda cat, ns, tbl, df, schema, **_: written.append(df),
        )
        quality_calls: list[tuple[int, str]] = []
        monkeypatch.setattr(
            silver_to_gold_features,
            "run_silver_quality_report",
            lambda df, layer: quality_calls.append((len(df), layer)),
        )

        result = silver_to_gold_features.run(_make_catalog())

        assert result["table"] == "iceberg:gold.ecb_dax_features"
        assert quality_calls == [(1, "ecb_dax_features")]
        assert written[0].columns.tolist() == [
            "event_date",
            "rate_change_bps",
            "rate_level_pct",
            "is_rate_hike",
            "is_rate_cut",
            "dax_pre_close",
            "dax_return_1d",
            "dax_return_5d",
            "dax_volatility_pre_5d",
        ]
