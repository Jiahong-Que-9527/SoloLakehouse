from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from transformations.build_eur_market_daily import build_eur_market_daily
from transformations.dax_bronze_to_silver import transform_dax_bronze_to_silver
from transformations.ecb_bronze_to_silver import transform_ecb_bronze_to_silver
from transformations.ecb_fx_bronze_to_silver import transform_ecb_fx_bronze_to_silver
from transformations.silver_to_gold_features import build_gold_features


class TestECBTransform:
    def test_transform_ecb_dedup_drops_null_rates(self) -> None:
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
        rate_change = out.loc[
            out["observation_date"] == dt.date(2024, 1, 2),
            "rate_change_bps",
        ].item()
        assert rate_change == 25.0

    def test_transform_ecb_prefers_dfr_when_present(self) -> None:
        df = pd.DataFrame(
            {
                "observation_date": ["2024-01-01", "2024-01-01", "2024-01-02", "2024-01-02"],
                "rate_pct": [4.0, 3.5, 4.25, 3.75],
                "rate_type": ["MRO", "DFR", "MRO", "DFR"],
                "_ingestion_timestamp": [dt.datetime.now(dt.timezone.utc)] * 4,
                "_source": ["ECB_SDW"] * 4,
            }
        )

        out = transform_ecb_bronze_to_silver(df)

        assert len(out) == 2
        assert out.iloc[0]["rate_pct"] == 3.5
        assert out.iloc[1]["rate_pct"] == 3.75


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


class TestECBFxTransform:
    def test_drops_inactive_currency_and_computes_return(self) -> None:
        df = pd.DataFrame(
            {
                "observation_date": [
                    "2024-01-02",
                    "2024-01-03",
                    "2024-01-02",
                    "2024-01-03",
                    "2023-01-02",
                ],
                "currency": ["USD", "USD", "GBP", "GBP", "BGN"],
                "fx_rate": [1.10, 1.12, 0.86, 0.87, 1.95],
                "_ingestion_timestamp": [dt.datetime.now(dt.timezone.utc)] * 5,
                "_source": ["ECB_SDW"] * 5,
            }
        )

        out = transform_ecb_fx_bronze_to_silver(df)

        assert set(out["currency"]) == {"USD", "GBP"}
        assert "BGN" not in set(out["currency"])
        usd = out[out["currency"] == "USD"].sort_values("observation_date")
        assert pd.isna(usd.iloc[0]["fx_return_pct"])
        assert usd.iloc[1]["fx_return_pct"] == pytest.approx((1.12 / 1.10 - 1.0) * 100.0)


class TestEurMarketDaily:
    def test_build_eur_market_daily_inner_fx_left_ewg_no_ffill(self) -> None:
        fx_rows: list[dict[str, object]] = []
        for day, rates in [
            ("2024-01-02", {"USD": 1.10, "GBP": 0.86, "CHF": 0.93, "JPY": 160.0, "CNY": 7.8}),
            ("2024-01-03", {"USD": 1.12, "GBP": 0.87, "CHF": 0.94, "JPY": 161.0, "CNY": 7.9}),
            ("2024-01-04", {"USD": 1.11, "GBP": 0.865, "CHF": 0.935, "JPY": 159.0, "CNY": 7.85}),
        ]:
            for currency, rate in rates.items():
                fx_rows.append(
                    {"observation_date": day, "currency": currency, "fx_rate": rate}
                )
        # Incomplete basket day should drop out of the inner join.
        fx_rows.append({"observation_date": "2024-01-05", "currency": "USD", "fx_rate": 1.13})
        fx = pd.DataFrame(fx_rows)
        ecb = pd.DataFrame(
            {
                "observation_date": ["2024-01-02", "2024-01-03", "2024-01-04"],
                "rate_pct": [4.0, 4.0, 4.25],
            }
        )
        ewg = pd.DataFrame(
            {
                "observation_date": ["2024-01-02", "2024-01-04"],
                "close_price": [30.0, 31.0],
            }
        )

        out = build_eur_market_daily(fx, ecb, ewg)

        assert list(out["observation_date"]) == [
            dt.date(2024, 1, 2),
            dt.date(2024, 1, 3),
            dt.date(2024, 1, 4),
        ]
        assert out.loc[0, "ewg_close_eur"] == pytest.approx(30.0 / 1.10)
        assert pd.isna(out.loc[1, "ewg_close_usd"])
        assert pd.isna(out.loc[1, "ewg_price_date"])
        assert out.loc[2, "ewg_price_date"] == dt.date(2024, 1, 4)
        assert out.loc[2, "ecb_policy_rate_pct"] == 4.25
        assert out.loc[1, "eur_usd_return_pct_1d"] == pytest.approx((1.12 / 1.10 - 1.0) * 100.0)
