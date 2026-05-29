"""DAX Bronze-to-Silver transformation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from ingestion.iceberg_io import overwrite_table, scan_table
from ingestion.iceberg_schemas import SILVER_DAX_DAILY_SCHEMA
from transformations.quality_report import run_silver_quality_report

if TYPE_CHECKING:
    from pyiceberg.catalog import Catalog


def transform_dax_bronze_to_silver(df: pd.DataFrame) -> pd.DataFrame:
    """Transform DAX bronze rows into cleaned silver rows."""
    transformed = df.copy()

    transformed["observation_date"] = pd.to_datetime(
        transformed["observation_date"], errors="coerce"
    ).dt.date
    for column in ["open_price", "high_price", "low_price", "close_price", "volume"]:
        transformed[column] = pd.to_numeric(transformed[column], errors="coerce")

    weekday_series = pd.to_datetime(transformed["observation_date"], errors="coerce").dt.dayofweek
    transformed = transformed[weekday_series < 5]
    transformed = transformed.sort_values("observation_date")
    transformed["daily_return"] = (
        (transformed["close_price"] / transformed["close_price"].shift(1) - 1.0) * 100
    ).round(4)
    transformed = transformed.drop_duplicates(subset=["observation_date"], keep="last")
    transformed = transformed.drop(columns=["_ingestion_timestamp", "_source"], errors="ignore")

    return transformed[
        [
            "observation_date",
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "volume",
            "daily_return",
        ]
    ]


def run(catalog: "Catalog") -> dict[str, object]:
    """Read DAX bronze Iceberg table, transform, write to silver, return summary."""
    bronze_df = scan_table(catalog, "bronze", "dax_daily")

    if bronze_df.empty:
        raise ValueError("No DAX bronze records found in Iceberg table")

    silver_df = transform_dax_bronze_to_silver(bronze_df)
    run_silver_quality_report(silver_df, "dax_daily_cleaned")

    overwrite_table(catalog, "silver", "dax_daily_cleaned", silver_df, SILVER_DAX_DAILY_SCHEMA)

    return {"table": "iceberg:silver.dax_daily_cleaned", "row_count": len(silver_df)}
