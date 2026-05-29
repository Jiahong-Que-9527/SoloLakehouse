"""Collector for ECB MRO rate data."""

from __future__ import annotations

import datetime as dt
import time
from typing import TYPE_CHECKING, Any

import pandas as pd
import requests
import structlog
from pydantic import ValidationError

from ingestion import iceberg_io
from ingestion.bronze_writer import BronzeWriter
from ingestion.exceptions import CollectorUnavailableError
from ingestion.quality.bronze_checks import run_ecb_bronze_checks
from ingestion.schema.ecb_schema import ECBRecord
from storage_config import get_data_bucket

if TYPE_CHECKING:
    from pyiceberg.catalog import Catalog

logger = structlog.get_logger()


class ECBCollector:
    """Collect, validate, and write ECB data to Bronze (Iceberg)."""

    ENDPOINT = "https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.MRR_RT.LEV"

    def __init__(self, catalog: "Catalog", bucket: str | None = None, force: bool = False):
        self.catalog = catalog
        self.bucket = bucket or get_data_bucket()
        self.force = force
        self.bronze_writer = BronzeWriter(catalog=catalog, bucket=self.bucket)

    def _fetch_data(self) -> list[dict[str, Any]]:
        params = {"format": "jsondata", "startPeriod": "1999-01-01"}
        last_error: Exception | None = None

        for attempt in range(1, 4):
            try:
                response = requests.get(self.ENDPOINT, params=params, timeout=10)
                response.raise_for_status()
                payload = response.json()
                return self._parse_payload(payload)
            except Exception as exc:  # pragma: no cover - exercised in tests via mocking
                last_error = exc
                if attempt < 3:
                    time.sleep(2)

        raise CollectorUnavailableError(
            f"ECB source unreachable after 3 retries: {last_error}"
        ) from last_error

    def _parse_payload(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
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

        records: list[dict] = []
        series_map = payload.get("dataSets", [{}])[0].get("series", {})
        for series in series_map.values():
            observations = series.get("observations", {})
            for obs_idx, obs_value in observations.items():
                obs_date = index_to_date.get(str(obs_idx))
                value = obs_value[0] if isinstance(obs_value, list) and obs_value else None
                records.append(
                    {
                        "observation_date": obs_date,
                        "rate_pct": value,
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
                parsed = ECBRecord(**record)
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
            df = iceberg_io.scan_table(self.catalog, "bronze", "ecb_rates")
            if df.empty:
                return False
            max_ts = pd.to_datetime(df["_ingestion_timestamp"], utc=True).max()
            return max_ts.date() == dt.date.today()
        except NoSuchTableError:
            return False

    def collect(self) -> dict[str, Any]:
        if not self.force and self._already_ingested_today():
            logger.info("ecb_already_ingested_today")
            return {"status": "skipped", "reason": "already_ingested_today"}

        logger.info("ecb_fetch_started")
        raw_data = self._fetch_data()
        valid, rejected = self._validate_records(raw_data)
        logger.info(
            "ecb_validation_complete",
            valid_count=len(valid),
            rejected_count=len(rejected),
        )

        if not valid:
            raise ValueError("No valid ECB records after validation")

        valid_df = pd.DataFrame(valid)
        run_ecb_bronze_checks(valid_df)

        path = self.bronze_writer.write(valid_df, source="ecb_rates")
        rejected_path = self.bronze_writer.write_rejected(rejected, source="ECB")

        logger.info(
            "ecb_ingestion_complete",
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
