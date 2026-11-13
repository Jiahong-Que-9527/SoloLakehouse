from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock

import pandas as pd

from projects.finance.src import ecb_bronze_to_silver
from projects.finance.src.ecb_bronze_to_silver import transform_ecb_bronze_to_silver


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


class TestECBRun:
    def test_ecb_run_reads_bronze_and_writes_silver(self, monkeypatch) -> None:
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

        result = ecb_bronze_to_silver.run(MagicMock(name="catalog"))

        assert result["table"] == "iceberg:silver.ecb_rates_cleaned"
        assert result["row_count"] == 2
        assert quality_calls == [(2, "ecb_rates_cleaned")]
        assert written[0].columns.tolist() == ["observation_date", "rate_pct", "rate_change_bps"]
