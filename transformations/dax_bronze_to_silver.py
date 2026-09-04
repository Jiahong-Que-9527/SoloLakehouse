"""German equity proxy Bronze-to-Silver transformation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from governance.contracts import contract_path, load_contract
from governance.quality import validate_dataset_quality
from ingestion.iceberg_io import overwrite_table, scan_table
from ingestion.iceberg_schemas import SILVER_GERMAN_EQUITY_PROXY_DAILY_SCHEMA
from transformations.quality_report import run_silver_quality_report

if TYPE_CHECKING:
    from pyiceberg.catalog import Catalog


def transform_german_equity_proxy_bronze_to_silver(df: pd.DataFrame) -> pd.DataFrame:
    """Transform EWG bronze rows into cleaned silver rows."""
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


# Backward-compatible alias for tests and imports during the L4 rename.
transform_dax_bronze_to_silver = transform_german_equity_proxy_bronze_to_silver


def run(catalog: "Catalog") -> dict[str, object]:
    """Read EWG bronze Iceberg table, transform, write to silver, return summary."""
    bronze_df = scan_table(catalog, "bronze", "german_equity_proxy_daily")

    if bronze_df.empty:
        raise ValueError("No German equity proxy bronze records found in Iceberg table")

    silver_df = transform_german_equity_proxy_bronze_to_silver(bronze_df)
    run_silver_quality_report(silver_df, "german_equity_proxy_daily_cleaned")
    validate_dataset_quality(
        silver_df,
        load_contract(contract_path("fin.german_equity_proxy_daily_silver")),
    )

    overwrite_table(
        catalog,
        "silver",
        "german_equity_proxy_daily_cleaned",
        silver_df,
        SILVER_GERMAN_EQUITY_PROXY_DAILY_SCHEMA,
    )

    return {
        "table": "iceberg:silver.german_equity_proxy_daily_cleaned",
        "row_count": len(silver_df),
    }
