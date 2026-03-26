from __future__ import annotations

import datetime as dt

import pandas as pd

from transformations.dax_bronze_to_silver import transform_dax_bronze_to_silver
from transformations.ecb_bronze_to_silver import transform_ecb_bronze_to_silver
from transformations.silver_to_gold_features import build_gold_features


class TestECBTransform:
    def test_transform_ecb_forward_fill_and_dedup(self) -> None:
        df = pd.DataFrame(
            {
                "observation_date": ["2024-01-01", "2024-01-02", "2024-01-02", "2024-01-03"],
                "rate_pct": [4.0, None, 4.25, 4.25],
                "_ingestion_timestamp": [dt.datetime.now(dt.timezone.utc)] * 4,
                "_source": ["ECB_SDW"] * 4,
            }
        )

        out = transform_ecb_bronze_to_silver(df)

        assert "rate_change_bps" in out.columns
        assert len(out) == 3
        assert out["rate_pct"].isnull().sum() == 0
        assert out["observation_date"].duplicated().sum() == 0


class TestDAXTransform:
    def test_transform_dax_weekend_removed_and_daily_return(self) -> None:
        df = pd.DataFrame(
            {
                "observation_date": ["2024-01-05", "2024-01-06", "2024-01-08"],  # Fri, Sat, Mon
                "open_price": [100, 101, 102],
                "high_price": [101, 102, 103],
                "low_price": [99, 100, 101],
                "close_price": [100, 101, 103],
                "volume": [1000, 1000, 1000],
                "_ingestion_timestamp": [dt.datetime.now(dt.timezone.utc)] * 3,
                "_source": ["DAX_SAMPLE"] * 3,
            }
        )

        out = transform_dax_bronze_to_silver(df)

        assert len(out) == 2
        assert "daily_return" in out.columns
        assert out.columns.tolist() == [
            "observation_date",
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "volume",
            "daily_return",
        ]


class TestGoldFeatures:
    def test_build_gold_features_event_rows_only_and_columns_present(self) -> None:
        ecb = pd.DataFrame(
            {
                "observation_date": ["2024-01-10", "2024-01-11"],
                "rate_pct": [4.0, 4.25],
                "rate_change_bps": [0.0, 25.0],
            }
        )

        dates = pd.date_range("2024-01-02", periods=20, freq="B")
        dax = pd.DataFrame(
            {
                "observation_date": dates.date,
                "close_price": [100 + i for i in range(20)],
                "daily_return": [0.1 + i * 0.01 for i in range(20)],
            }
        )

        out = build_gold_features(ecb, dax)

        assert len(out) == 1
        assert (out["rate_change_bps"] != 0).all()
        assert {
            "event_date",
            "rate_change_bps",
            "rate_level_pct",
            "is_rate_hike",
            "is_rate_cut",
            "dax_pre_close",
            "dax_return_1d",
            "dax_return_5d",
            "dax_volatility_pre_5d",
        } <= set(out.columns)

    def test_build_gold_features_drops_events_without_dax_data(self) -> None:
        ecb = pd.DataFrame(
            {
                "observation_date": ["2024-01-10", "2024-12-31"],
                "rate_pct": [4.0, 4.25],
                "rate_change_bps": [25.0, -25.0],
            }
        )
        dates = pd.date_range("2024-01-02", periods=20, freq="B")
        dax = pd.DataFrame(
            {
                "observation_date": dates.date,
                "close_price": [100 + i for i in range(20)],
                "daily_return": [0.1 + i * 0.01 for i in range(20)],
            }
        )

        out = build_gold_features(ecb, dax)
        assert len(out) == 1
