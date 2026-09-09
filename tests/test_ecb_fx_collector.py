"""Unit tests for ECB EXR FX collector and schema."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest
from pydantic import ValidationError

from ingestion.collectors.ecb_fx_collector import ECBFxCollector
from ingestion.exceptions import CollectorUnavailableError
from ingestion.schema.ecb_fx_schema import ECBFxRecord

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "ecb_exr_daily_sample.json"


def _make_catalog() -> MagicMock:
    return MagicMock(name="catalog")


class TestECBFxRecord:
    def test_valid_record_parses(self) -> None:
        model = ECBFxRecord(
            observation_date="2024-01-02",
            currency="usd",
            fx_rate=1.09,
        )
        assert model.currency == "USD"
        assert model.source == "ECB_SDW"

    def test_non_positive_fx_rate_raises(self) -> None:
        with pytest.raises(ValidationError):
            ECBFxRecord(observation_date="2024-01-02", currency="USD", fx_rate=0.0)

    def test_future_date_raises(self) -> None:
        future = dt.date.today() + dt.timedelta(days=1)
        with pytest.raises(ValidationError):
            ECBFxRecord(observation_date=future, currency="USD", fx_rate=1.1)

    def test_model_dump_aliases(self) -> None:
        dumped = ECBFxRecord(
            observation_date="2024-01-02",
            currency="USD",
            fx_rate=1.1,
        ).model_dump(by_alias=True)
        assert {"_ingestion_timestamp", "_source"} <= set(dumped)


class TestECBFxCollector:
    def test_parse_fixture_resolves_currency_from_series_key(self) -> None:
        collector = ECBFxCollector(catalog=_make_catalog(), fixture_path=FIXTURE_PATH)
        payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        records = collector._parse_payload(payload)

        currencies = {record["currency"] for record in records}
        assert currencies == {"BGN", "CHF", "GBP", "USD"}
        assert len(records) == 16  # 4 currencies × 4 days
        usd = [
            record
            for record in records
            if record["currency"] == "USD" and record["observation_date"] == "2024-01-02"
        ]
        assert len(usd) == 1
        assert usd[0]["fx_rate"] == pytest.approx(1.0956)

    def test_fetch_data_uses_fixture_path(self) -> None:
        collector = ECBFxCollector(catalog=_make_catalog(), fixture_path=FIXTURE_PATH)
        records = collector._fetch_data()
        assert len(records) == 16

    def test_fetch_data_uses_env_fixture(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ECB_FX_FIXTURE_PATH", str(FIXTURE_PATH))
        collector = ECBFxCollector(catalog=_make_catalog())
        assert collector.fixture_path == FIXTURE_PATH
        assert len(collector._fetch_data()) == 16

    def test_fetch_live_retries_then_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        collector = ECBFxCollector(catalog=_make_catalog())
        monkeypatch.setattr(
            "ingestion.collectors.ecb_fx_collector.requests.get",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("down")),
        )
        monkeypatch.setattr("ingestion.collectors.ecb_fx_collector.time.sleep", lambda *_: None)

        with pytest.raises(CollectorUnavailableError):
            collector._fetch_live()

    def test_validate_records_splits_valid_and_rejected(self) -> None:
        collector = ECBFxCollector(catalog=_make_catalog())
        tomorrow = (dt.date.today() + dt.timedelta(days=1)).isoformat()
        valid, rejected = collector._validate_records(
            [
                {"observation_date": "2024-01-02", "currency": "USD", "fx_rate": 1.1},
                {"observation_date": tomorrow, "currency": "USD", "fx_rate": 1.1},
            ]
        )
        assert len(valid) == 1
        assert len(rejected) == 1

    def test_collect_writes_via_bronze_writer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        collector = ECBFxCollector(catalog=_make_catalog(), fixture_path=FIXTURE_PATH, force=True)
        monkeypatch.setattr(
            "ingestion.collectors.ecb_fx_collector.run_ecb_fx_bronze_checks",
            lambda df: None,
        )
        collector.bronze_writer = MagicMock()
        collector.bronze_writer.write.return_value = "iceberg:bronze.ecb_fx_rates"
        collector.bronze_writer.write_rejected.return_value = None

        result = collector.collect()

        assert result["status"] == "ok"
        assert result["valid_count"] == 16
        collector.bronze_writer.write.assert_called_once()
        written = collector.bronze_writer.write.call_args.args[0]
        assert isinstance(written, pd.DataFrame)
        assert set(written["currency"]) == {"BGN", "CHF", "GBP", "USD"}
