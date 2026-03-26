from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from ingestion.schema.dax_schema import DAXRecord
from ingestion.schema.ecb_schema import ECBRecord


def make_ecb_record(**overrides) -> dict:
    record = {
        "observation_date": "2024-01-15",
        "rate_pct": 4.5,
    }
    record.update(overrides)
    return record


def make_dax_record(**overrides) -> dict:
    record = {
        "observation_date": "2024-01-15",
        "open_price": 16800.0,
        "high_price": 16920.0,
        "low_price": 16780.0,
        "close_price": 16890.0,
        "volume": 9.1e7,
    }
    record.update(overrides)
    return record


class TestECBRecord:
    def test_valid_record_parses(self) -> None:
        model = ECBRecord(**make_ecb_record())
        assert model.rate_pct == 4.5

    def test_invalid_rate_pct_raises(self) -> None:
        with pytest.raises(ValidationError):
            ECBRecord(**make_ecb_record(rate_pct=25.0))

    def test_future_date_raises(self) -> None:
        future = dt.date.today() + dt.timedelta(days=1)
        with pytest.raises(ValidationError):
            ECBRecord(**make_ecb_record(observation_date=future.isoformat()))

    def test_model_dump_keys(self) -> None:
        model = ECBRecord(**make_ecb_record())
        dumped = model.model_dump(by_alias=True)
        assert {"observation_date", "rate_pct", "_ingestion_timestamp", "_source"} <= set(dumped)


class TestDAXRecord:
    def test_valid_record_parses(self) -> None:
        model = DAXRecord(**make_dax_record())
        assert model.close_price > 0

    def test_future_date_raises(self) -> None:
        future = dt.date.today() + dt.timedelta(days=1)
        with pytest.raises(ValidationError):
            DAXRecord(**make_dax_record(observation_date=future.isoformat()))

    def test_high_price_lower_than_low_price_raises(self) -> None:
        with pytest.raises(ValidationError):
            DAXRecord(**make_dax_record(high_price=100.0, low_price=200.0))

    def test_model_dump_keys(self) -> None:
        model = DAXRecord(**make_dax_record())
        dumped = model.model_dump(by_alias=True)
        assert {
            "observation_date",
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "volume",
            "_ingestion_timestamp",
            "_source",
        } <= set(dumped)
