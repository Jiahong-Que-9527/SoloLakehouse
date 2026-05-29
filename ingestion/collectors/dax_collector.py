"""Collector for DAX sample daily OHLCV data."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any

import pandas as pd
import structlog
from pydantic import ValidationError

from ingestion import iceberg_io
from ingestion.bronze_writer import BronzeWriter
from ingestion.quality.bronze_checks import run_dax_bronze_checks
from ingestion.schema.dax_schema import DAXRecord
from storage_config import get_data_bucket

if TYPE_CHECKING:
    from pyiceberg.catalog import Catalog

logger = structlog.get_logger()


class DAXCollector:
    """Collect, validate, and write DAX data to Bronze (Iceberg)."""

    def __init__(
        self,
        catalog: "Catalog",
        csv_path: str = "data/sample/dax_daily_sample.csv",
        bucket: str | None = None,
        force: bool = False,
    ):
        self.catalog = catalog
        self.csv_path = csv_path
        self.bucket = bucket or get_data_bucket()
        self.force = force
        self.bronze_writer = BronzeWriter(catalog=catalog, bucket=self.bucket)

    def _fetch_data(self) -> list[dict[str, Any]]:
        rename_map = {
            "date": "observation_date",
            "open": "open_price",
            "high": "high_price",
            "low": "low_price",
            "close": "close_price",
            "volume": "volume",
        }
        frame = pd.read_csv(self.csv_path)
        frame = frame.rename(columns=rename_map)
        return frame.to_dict(orient="records")

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
            df = iceberg_io.scan_table(self.catalog, "bronze", "dax_daily")
            if df.empty:
                return False
            max_ts = pd.to_datetime(df["_ingestion_timestamp"], utc=True).max()
            return max_ts.date() == dt.date.today()
        except NoSuchTableError:
            return False

    def collect(self) -> dict[str, Any]:
        if not self.force and self._already_ingested_today():
            logger.info("dax_already_ingested_today")
            return {"status": "skipped", "reason": "already_ingested_today"}

        logger.info("dax_fetch_started")
        raw_data = self._fetch_data()
        valid, rejected = self._validate_records(raw_data)
        logger.info(
            "dax_validation_complete",
            valid_count=len(valid),
            rejected_count=len(rejected),
        )

        if not valid:
            raise ValueError("No valid DAX records after validation")

        valid_df = pd.DataFrame(valid)
        run_dax_bronze_checks(valid_df)

        path = self.bronze_writer.write(valid_df, source="dax_daily")
        rejected_path = self.bronze_writer.write_rejected(rejected, source="DAX")

        logger.info(
            "dax_ingestion_complete",
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
