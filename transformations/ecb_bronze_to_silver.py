"""ECB Bronze-to-Silver transformation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from ingestion.iceberg_io import overwrite_table, scan_table
from ingestion.iceberg_schemas import SILVER_ECB_RATES_SCHEMA
from transformations.quality_report import run_silver_quality_report

if TYPE_CHECKING:
    from pyiceberg.catalog import Catalog


def transform_ecb_bronze_to_silver(df: pd.DataFrame) -> pd.DataFrame:
    """Transform ECB bronze rows into cleaned silver rows."""
    transformed = df.copy()

    if "type" in transformed.columns:
        type_values = transformed["type"].astype(str)
        transformed = transformed[
            type_values.str.contains("MRO", case=False, na=False)
            | type_values.str.contains("Main Refinancing Operations", case=False, na=False)
        ]

    transformed["observation_date"] = pd.to_datetime(
        transformed["observation_date"], errors="coerce"
    ).dt.date
    transformed["rate_pct"] = pd.to_numeric(transformed["rate_pct"], errors="coerce")

    transformed = transformed.sort_values("observation_date")
    transformed["rate_pct"] = transformed["rate_pct"].ffill()
    transformed = transformed.drop_duplicates(subset=["observation_date"], keep="last")
    transformed = transformed.drop(columns=["_ingestion_timestamp", "_source"], errors="ignore")
    transformed["rate_change_bps"] = (
        (transformed["rate_pct"] - transformed["rate_pct"].shift(1)) * 100
    ).round(1)

    return transformed[["observation_date", "rate_pct", "rate_change_bps"]]


def run(catalog: "Catalog") -> dict[str, object]:
    """Read ECB bronze Iceberg table, transform, write to silver, return summary."""
    bronze_df = scan_table(catalog, "bronze", "ecb_rates")

    if bronze_df.empty:
        raise ValueError("No ECB bronze records found in Iceberg table")

    silver_df = transform_ecb_bronze_to_silver(bronze_df)
    run_silver_quality_report(silver_df, "ecb_rates_cleaned")

    overwrite_table(catalog, "silver", "ecb_rates_cleaned", silver_df, SILVER_ECB_RATES_SCHEMA)

    return {"table": "iceberg:silver.ecb_rates_cleaned", "row_count": len(silver_df)}
