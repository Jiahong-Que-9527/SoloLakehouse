"""Iceberg schema and partition spec definitions for all medallion layers."""

from __future__ import annotations

from pyiceberg.partitioning import PartitionField, PartitionSpec
from pyiceberg.schema import Schema
from pyiceberg.transforms import DayTransform
from pyiceberg.types import (
    BooleanType,
    DateType,
    DoubleType,
    NestedField,
    StringType,
    TimestamptzType,
)

# ── Bronze ───────────────────────────────────────────────────────────────────

BRONZE_ECB_RATES_SCHEMA = Schema(
    NestedField(1, "observation_date", DateType(), required=False),
    NestedField(2, "rate_pct", DoubleType(), required=False),
    NestedField(3, "_ingestion_timestamp", TimestamptzType(), required=False),
    NestedField(4, "_source", StringType(), required=False),
)

BRONZE_ECB_RATES_PARTITION = PartitionSpec(
    PartitionField(source_id=3, field_id=1000, transform=DayTransform(), name="ingestion_day"),
)

BRONZE_DAX_DAILY_SCHEMA = Schema(
    NestedField(1, "observation_date", DateType(), required=False),
    NestedField(2, "open_price", DoubleType(), required=False),
    NestedField(3, "high_price", DoubleType(), required=False),
    NestedField(4, "low_price", DoubleType(), required=False),
    NestedField(5, "close_price", DoubleType(), required=False),
    NestedField(6, "volume", DoubleType(), required=False),
    NestedField(7, "_ingestion_timestamp", TimestamptzType(), required=False),
    NestedField(8, "_source", StringType(), required=False),
)

BRONZE_DAX_DAILY_PARTITION = PartitionSpec(
    PartitionField(source_id=7, field_id=1000, transform=DayTransform(), name="ingestion_day"),
)

# Rejected records are serialised to a narrow fixed schema; the original
# record fields are stored as a JSON string in `payload`.
BRONZE_REJECTED_SCHEMA = Schema(
    NestedField(1, "source", StringType(), required=False),
    NestedField(2, "rejection_reason", StringType(), required=False),
    NestedField(3, "payload", StringType(), required=False),
    NestedField(4, "_ingested_at", TimestamptzType(), required=False),
)

# ── Silver ───────────────────────────────────────────────────────────────────

SILVER_ECB_RATES_SCHEMA = Schema(
    NestedField(1, "observation_date", DateType(), required=False),
    NestedField(2, "rate_pct", DoubleType(), required=False),
    NestedField(3, "rate_change_bps", DoubleType(), required=False),
)

SILVER_DAX_DAILY_SCHEMA = Schema(
    NestedField(1, "observation_date", DateType(), required=False),
    NestedField(2, "open_price", DoubleType(), required=False),
    NestedField(3, "high_price", DoubleType(), required=False),
    NestedField(4, "low_price", DoubleType(), required=False),
    NestedField(5, "close_price", DoubleType(), required=False),
    NestedField(6, "volume", DoubleType(), required=False),
    NestedField(7, "daily_return", DoubleType(), required=False),
)

# ── Gold ─────────────────────────────────────────────────────────────────────

GOLD_FEATURES_SCHEMA = Schema(
    NestedField(1, "event_date", DateType(), required=False),
    NestedField(2, "rate_change_bps", DoubleType(), required=False),
    NestedField(3, "rate_level_pct", DoubleType(), required=False),
    NestedField(4, "is_rate_hike", BooleanType(), required=False),
    NestedField(5, "is_rate_cut", BooleanType(), required=False),
    NestedField(6, "dax_pre_close", DoubleType(), required=False),
    NestedField(7, "dax_return_1d", DoubleType(), required=False),
    NestedField(8, "dax_return_5d", DoubleType(), required=False),
    NestedField(9, "dax_volatility_pre_5d", DoubleType(), required=False),
)
