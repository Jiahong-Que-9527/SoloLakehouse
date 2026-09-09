"""Collector for ECB EXR daily euro reference FX rates (panel-shaped)."""

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
from ingestion.quality.bronze_checks import run_ecb_fx_bronze_checks
from ingestion.schema.ecb_fx_schema import ECBFxRecord
from storage_config import get_data_bucket

if TYPE_CHECKING:
    from pyiceberg.catalog import Catalog

logger = structlog.get_logger()

_EXR_ENDPOINT = "https://data-api.ecb.europa.eu/service/data/EXR/D..EUR.SP00.A"
_CURRENCY_DIM_INDEX = 1


class ECBFxCollector:
    """Collect, validate, and write ECB EXR panel data to Bronze (Iceberg)."""

    def __init__(
        self,
        catalog: "Catalog",
        fixture_path: str | Path | None = None,
        bucket: str | None = None,
        force: bool = False,
    ):
        self.catalog = catalog
        env_fixture = os.environ.get("ECB_FX_FIXTURE_PATH", "").strip()
        resolved_fixture = fixture_path or (env_fixture if env_fixture else None)
        self.fixture_path = Path(resolved_fixture) if resolved_fixture else None
        self.bucket = bucket or get_data_bucket()
        self.force = force
        self.bronze_writer = BronzeWriter(catalog=catalog, bucket=self.bucket)

    def _fetch_live(self) -> list[dict[str, Any]]:
        params = {"format": "jsondata", "startPeriod": "1999-01-01"}
        last_error: Exception | None = None

        for attempt in range(1, 4):
            try:
                response = requests.get(_EXR_ENDPOINT, params=params, timeout=60)
                response.raise_for_status()
                payload = response.json()
                return self._parse_payload(payload)
            except Exception as exc:  # pragma: no cover - exercised in tests via mocking
                last_error = exc
                if attempt < 3:
                    time.sleep(2)

        raise CollectorUnavailableError(
            f"ECB EXR source unreachable after 3 retries: {last_error}"
        ) from last_error

    def _fetch_data(self) -> list[dict[str, Any]]:
        if self.fixture_path is not None:
            payload = json.loads(self.fixture_path.read_text(encoding="utf-8"))
            return self._parse_payload(payload)
        return self._fetch_live()

    def _parse_payload(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse SDMX-JSON EXR panel, resolving currency from series key position 1."""
        series_dims = (
            payload.get("structure", {})
            .get("dimensions", {})
            .get("series", [])
        )
        if len(series_dims) <= _CURRENCY_DIM_INDEX:
            raise ValueError("ECB EXR payload missing CURRENCY series dimension")

        currency_values = series_dims[_CURRENCY_DIM_INDEX].get("values", [])
        index_to_currency = {
            idx: str(entry.get("id", "")).upper()
            for idx, entry in enumerate(currency_values)
            if entry.get("id")
        }

        observation_values = (
            payload.get("structure", {})
            .get("dimensions", {})
            .get("observation", [{}])[0]
            .get("values", [])
        )
        index_to_date = {
            str(idx): entry.get("id")
            for idx, entry in enumerate(observation_values)
            if entry.get("id")
        }

        records: list[dict[str, Any]] = []
        series_map = payload.get("dataSets", [{}])[0].get("series", {})
        for series_key, series in series_map.items():
            key_parts = str(series_key).split(":")
            if len(key_parts) <= _CURRENCY_DIM_INDEX:
                continue
            try:
                currency_idx = int(key_parts[_CURRENCY_DIM_INDEX])
            except ValueError:
                continue
            currency = index_to_currency.get(currency_idx)
            if not currency:
                continue

            observations = series.get("observations", {})
            for obs_idx, obs_value in observations.items():
                obs_date = index_to_date.get(str(obs_idx))
                value = obs_value[0] if isinstance(obs_value, list) and obs_value else None
                records.append(
                    {
                        "observation_date": obs_date,
                        "currency": currency,
                        "fx_rate": value,
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
                parsed = ECBFxRecord(**record)
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
            df = iceberg_io.scan_table(self.catalog, "bronze", "ecb_fx_rates")
            if df.empty:
                return False
            max_ts = pd.to_datetime(df["_ingestion_timestamp"], utc=True).max()
            return max_ts.date() == dt.date.today()
        except NoSuchTableError:
            return False

    def collect(self) -> dict[str, Any]:
        if not self.force and self._already_ingested_today():
            logger.info("ecb_fx_already_ingested_today")
            return {"status": "skipped", "reason": "already_ingested_today"}

        logger.info(
            "ecb_fx_fetch_started",
            fixture=str(self.fixture_path) if self.fixture_path else None,
        )
        raw_data = self._fetch_data()
        valid, rejected = self._validate_records(raw_data)
        logger.info(
            "ecb_fx_validation_complete",
            valid_count=len(valid),
            rejected_count=len(rejected),
        )

        if not valid:
            raise ValueError("No valid ECB FX records after validation")

        valid_df = pd.DataFrame(valid)
        run_ecb_fx_bronze_checks(valid_df)

        path = self.bronze_writer.write(valid_df, source="ecb_fx_rates")
        rejected_path = self.bronze_writer.write_rejected(rejected, source="ECB_FX")

        logger.info(
            "ecb_fx_ingestion_complete",
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
