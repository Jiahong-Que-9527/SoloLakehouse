"""Collector for DAX sample daily OHLCV data."""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

import pandas as pd
import structlog
from pydantic import ValidationError

from ingestion.bronze_writer import BronzeWriter
from ingestion.quality.bronze_checks import run_dax_bronze_checks
from ingestion.schema.dax_schema import DAXRecord

logger = structlog.get_logger()


class DAXCollector:
    """Collect, validate, and write DAX data to Bronze."""

    def __init__(
        self,
        minio_client: Any,
        csv_path: str = "data/sample/dax_daily_sample.csv",
        bucket: str = "sololakehouse",
        force: bool = False,
    ):
        self.minio = minio_client
        self.csv_path = csv_path
        self.bucket = bucket
        self.force = force
        self.bronze_writer = BronzeWriter(minio_client=minio_client, bucket=bucket)

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
        today = dt.date.today().isoformat()
        pattern = re.compile(r"ingestion_date=(\d{4}-\d{2}-\d{2})/")
        latest_partition: str | None = None

        objects = self.minio.list_objects(
            self.bucket,
            prefix="bronze/dax_daily/",
            recursive=True,
        )
        for obj in objects:
            match = pattern.search(obj.object_name)
            if match:
                date_str = match.group(1)
                if latest_partition is None or date_str > latest_partition:
                    latest_partition = date_str

        return latest_partition == today

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
