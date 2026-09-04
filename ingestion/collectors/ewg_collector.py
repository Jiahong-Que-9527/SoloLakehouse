"""Collector for EWG (German equity proxy) daily OHLCV via Alpha Vantage."""

from __future__ import annotations

import datetime as dt
import json
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
import requests
import structlog
from pydantic import ValidationError

from ingestion import iceberg_io
from ingestion.bronze_writer import BronzeWriter
from ingestion.exceptions import CollectorUnavailableError
from ingestion.quality.bronze_checks import run_german_equity_proxy_bronze_checks
from ingestion.schema.dax_schema import DAXRecord
from storage_config import get_data_bucket

if TYPE_CHECKING:
    from pyiceberg.catalog import Catalog

logger = structlog.get_logger()

DEFAULT_FIXTURE_PATH = Path("tests/fixtures/alpha_vantage_ewg_daily.json")
DEFAULT_BOOTSTRAP_PATH = Path("tests/fixtures/ewg_historical_bootstrap.json")


class EWGCollector:
    """Collect, validate, and write EWG market-proxy data to Bronze (Iceberg)."""

    API_URL = "https://www.alphavantage.co/query"

    def __init__(
        self,
        catalog: "Catalog",
        fixture_path: str | Path | None = None,
        bucket: str | None = None,
        force: bool = False,
    ):
        self.catalog = catalog
        env_fixture = os.environ.get("DAX_FIXTURE_PATH", "").strip()
        resolved_fixture = fixture_path or (env_fixture if env_fixture else None)
        self.fixture_path = Path(resolved_fixture) if resolved_fixture else None
        self.bucket = bucket or get_data_bucket()
        self.force = force
        self.bronze_writer = BronzeWriter(catalog=catalog, bucket=self.bucket)

    def _load_api_key(self) -> str:
        key = os.environ.get("ALPHA_VANTAGE_API_KEY", "").strip()
        if key:
            return key
        raise CollectorUnavailableError(
            "ALPHA_VANTAGE_API_KEY is required for live EWG ingestion"
        )

    def _fetch_live_alpha_vantage(self) -> list[dict[str, Any]]:
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": "EWG",
            "outputsize": "compact",
            "apikey": self._load_api_key(),
        }
        last_error: Exception | None = None

        for attempt in range(1, 4):
            try:
                response = requests.get(self.API_URL, params=params, timeout=30)
                response.raise_for_status()
                payload = response.json()
                if "Note" in payload or "Information" in payload:
                    raise CollectorUnavailableError(
                        f"Alpha Vantage rate limit or quota response: {payload}"
                    )
                return self._parse_alpha_vantage_payload(payload)
            except CollectorUnavailableError:
                raise
            except Exception as exc:  # pragma: no cover - exercised in tests via mocking
                last_error = exc
                if attempt < 3:
                    time.sleep(2)

        raise CollectorUnavailableError(
            f"Alpha Vantage source unreachable after 3 retries: {last_error}"
        ) from last_error

    def _load_bootstrap_records(self) -> list[dict[str, Any]]:
        bootstrap_env = os.environ.get("EWG_BOOTSTRAP_FIXTURE_PATH", "").strip()
        bootstrap_path = Path(bootstrap_env) if bootstrap_env else DEFAULT_BOOTSTRAP_PATH
        if not bootstrap_path.is_file():
            return []
        payload = json.loads(bootstrap_path.read_text(encoding="utf-8"))
        return self._parse_alpha_vantage_payload(payload)

    def _merge_live_with_bootstrap(
        self,
        live_records: list[dict[str, Any]],
        bootstrap_records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {
            str(record["observation_date"]): record for record in bootstrap_records
        }
        for record in live_records:
            merged[str(record["observation_date"])] = record
        return list(merged.values())

    def _fetch_data(self) -> list[dict[str, Any]]:
        if self.fixture_path is not None:
            payload = json.loads(self.fixture_path.read_text(encoding="utf-8"))
            return self._parse_alpha_vantage_payload(payload)

        live_records = self._fetch_live_alpha_vantage()
        bootstrap_records = self._load_bootstrap_records()
        if not bootstrap_records:
            return live_records
        merged = self._merge_live_with_bootstrap(live_records, bootstrap_records)
        logger.info(
            "ewg_bootstrap_merged",
            live_count=len(live_records),
            bootstrap_count=len(bootstrap_records),
            merged_count=len(merged),
        )
        return merged

    def _parse_alpha_vantage_payload(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        series = payload.get("Time Series (Daily)")
        if not isinstance(series, dict):
            raise ValueError("Alpha Vantage payload missing Time Series (Daily)")

        records: list[dict[str, Any]] = []
        for observation_date, ohlcv in series.items():
            if not isinstance(ohlcv, dict):
                continue
            records.append(
                {
                    "observation_date": observation_date,
                    "open_price": ohlcv.get("1. open"),
                    "high_price": ohlcv.get("2. high"),
                    "low_price": ohlcv.get("3. low"),
                    "close_price": ohlcv.get("4. close"),
                    "volume": ohlcv.get("5. volume"),
                }
            )
        return records

    def _validate_records(
        self, raw_data: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        valid: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []

        for record in raw_data:
            try:
                parsed = DAXRecord(**record)
                valid.append(parsed.model_dump(by_alias=True))
            except ValidationError as exc:
                rejected_record = dict(record)
                rejected_record["rejection_reason"] = str(exc)
                rejected.append(rejected_record)

        return valid, rejected

    def _already_ingested_today(self) -> bool:
        """Return True if Bronze already contains a row ingested today."""
        from pyiceberg.exceptions import NoSuchTableError

        try:
            df = iceberg_io.scan_table(self.catalog, "bronze", "german_equity_proxy_daily")
            if df.empty:
                return False
            max_ts = pd.to_datetime(df["_ingestion_timestamp"], utc=True).max()
            return max_ts.date() == dt.date.today()
        except NoSuchTableError:
            return False

    def collect(self) -> dict[str, Any]:
        if not self.force and self._already_ingested_today():
            logger.info("ewg_already_ingested_today")
            return {"status": "skipped", "reason": "already_ingested_today"}

        logger.info(
            "ewg_fetch_started",
            fixture=str(self.fixture_path) if self.fixture_path else None,
        )
        raw_data = self._fetch_data()
        valid, rejected = self._validate_records(raw_data)
        logger.info(
            "ewg_validation_complete",
            valid_count=len(valid),
            rejected_count=len(rejected),
        )

        if not valid:
            raise ValueError("No valid EWG records after validation")

        valid_df = pd.DataFrame(valid)
        run_german_equity_proxy_bronze_checks(valid_df)

        path = self.bronze_writer.write(valid_df, source="german_equity_proxy_daily")
        rejected_path = self.bronze_writer.write_rejected(rejected, source="EWG")

        logger.info(
            "ewg_ingestion_complete",
            valid_count=len(valid),
            rejected_count=len(rejected),
            path=path,
            rejected_path=rejected_path,
        )
        return {
            "status": "ok",
            "valid_count": len(valid),
            "rejected_count": len(rejected),
            "path": path,
            "rejected_path": rejected_path,
        }
