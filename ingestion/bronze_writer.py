"""Bronze-layer Iceberg writer for SoloLakehouse."""

from __future__ import annotations

import datetime as dt
import json
from typing import TYPE_CHECKING, Any

import pandas as pd
import structlog

from ingestion import iceberg_io
from ingestion.iceberg_schemas import (
    BRONZE_DAX_DAILY_PARTITION,
    BRONZE_DAX_DAILY_SCHEMA,
    BRONZE_ECB_RATES_PARTITION,
    BRONZE_ECB_RATES_SCHEMA,
    BRONZE_REJECTED_SCHEMA,
)
from storage_config import get_data_bucket

if TYPE_CHECKING:
    from pyiceberg.catalog import Catalog

logger = structlog.get_logger()

# Maps source name → (Iceberg schema, partition spec)
_BRONZE_TABLE_META = {
    "ecb_rates": (BRONZE_ECB_RATES_SCHEMA, BRONZE_ECB_RATES_PARTITION),
    "dax_daily": (BRONZE_DAX_DAILY_SCHEMA, BRONZE_DAX_DAILY_PARTITION),
}


class BronzeWriter:
    def __init__(self, catalog: "Catalog", bucket: str | None = None):
        self.catalog = catalog
        self.bucket = bucket or get_data_bucket()  # kept for observability logging

    def write(self, df: pd.DataFrame, source: str, ingestion_date: str | None = None) -> str:
        """Append *df* to the Bronze Iceberg table for *source* and return a logical path."""
        schema, partition_spec = _BRONZE_TABLE_META.get(source, (BRONZE_ECB_RATES_SCHEMA, None))

        iceberg_io.append_table(
            self.catalog,
            namespace="bronze",
            table_name=source,
            df=df,
            schema=schema,
            partition_spec=partition_spec,
        )
        path = f"iceberg:bronze.{source}"
        logger.info("bronze_written", source=source, rows=len(df), path=path)
        return path

    def write_rejected(
        self,
        records: list[dict[str, Any]],
        source: str,
        ingestion_date: str | None = None,
    ) -> str | None:
        """Append rejected records to the Bronze rejected Iceberg table."""
        if not records:
            return None

        for record in records:
            reason = record.get("rejection_reason")
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError("Each rejected record must include a non-empty rejection_reason")

        now = dt.datetime.now(dt.UTC)
        rows = []
        for rec in records:
            payload_dict = {k: v for k, v in rec.items() if k != "rejection_reason"}
            rows.append(
                {
                    "source": source,
                    "rejection_reason": rec["rejection_reason"],
                    "payload": json.dumps(payload_dict, default=str),
                    "_ingested_at": now,
                }
            )
        rejected_df = pd.DataFrame(rows)

        iceberg_io.append_table(
            self.catalog,
            namespace="bronze",
            table_name="rejected_records",
            df=rejected_df,
            schema=BRONZE_REJECTED_SCHEMA,
        )
        path = f"iceberg:bronze.rejected_records[source={source}]"
        logger.info("bronze_rejected_written", source=source, count=len(records))
        return path
