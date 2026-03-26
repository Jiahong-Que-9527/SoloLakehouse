from __future__ import annotations

import datetime as dt
import importlib
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pyarrow.parquet as pq

from transformations import dax_bronze_to_silver, ecb_bronze_to_silver, silver_to_gold_features


class FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def close(self) -> None:
        return None

    def release_conn(self) -> None:
        return None


def parquet_bytes(frame: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    frame.to_parquet(buffer, index=False)
    return buffer.getvalue()


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
        minio = MagicMock()
        minio.list_objects.return_value = [
            SimpleNamespace(object_name="bronze/ecb_rates/ingestion_date=2024-01-01/a.parquet")
        ]
        minio.get_object.return_value = FakeResponse(parquet_bytes(bronze))
        quality_calls: list[tuple[int, str]] = []
        monkeypatch.setattr(
            ecb_bronze_to_silver,
            "run_silver_quality_report",
            lambda df, layer: quality_calls.append((len(df), layer)),
        )

        path = ecb_bronze_to_silver.run(minio)

        assert path == "silver/ecb_rates_cleaned/ecb_rates_cleaned.parquet"
        assert quality_calls == [(2, "ecb_rates_cleaned")]
        args = minio.put_object.call_args.args
        written = pq.read_table(BytesIO(args[2].getvalue())).to_pandas()
        assert written.columns.tolist() == ["observation_date", "rate_pct", "rate_change_bps"]

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
        minio = MagicMock()
        minio.list_objects.return_value = [
            SimpleNamespace(object_name="bronze/dax_daily/ingestion_date=2024-01-05/a.parquet")
        ]
        minio.get_object.return_value = FakeResponse(parquet_bytes(bronze))
        quality_calls: list[tuple[int, str]] = []
        monkeypatch.setattr(
            dax_bronze_to_silver,
            "run_silver_quality_report",
            lambda df, layer: quality_calls.append((len(df), layer)),
        )

        path = dax_bronze_to_silver.run(minio)

        assert path == "silver/dax_daily_cleaned/dax_daily_cleaned.parquet"
        assert quality_calls == [(2, "dax_daily_cleaned")]
        args = minio.put_object.call_args.args
        written = pq.read_table(BytesIO(args[2].getvalue())).to_pandas()
        assert "daily_return" in written.columns

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
        minio = MagicMock()
        minio.get_object.side_effect = [
            FakeResponse(parquet_bytes(ecb)),
            FakeResponse(parquet_bytes(dax)),
        ]
        quality_calls: list[tuple[int, str]] = []
        monkeypatch.setattr(
            silver_to_gold_features,
            "run_silver_quality_report",
            lambda df, layer: quality_calls.append((len(df), layer)),
        )

        path = silver_to_gold_features.run(minio)

        assert path == "gold/rate_impact_features/ecb_dax_features.parquet"
        assert quality_calls == [(1, "ecb_dax_features")]
        args = minio.put_object.call_args.args
        written = pq.read_table(BytesIO(args[2].getvalue())).to_pandas()
        assert written.columns.tolist() == [
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
