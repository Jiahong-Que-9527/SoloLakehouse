"""ECB Bronze-to-Silver transformation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from governance.contracts import contract_path, load_contract
from governance.quality import validate_dataset_quality
from ingestion.iceberg_io import overwrite_table, scan_table
from ingestion.iceberg_schemas import SILVER_ECB_RATES_SCHEMA
from transformations.quality_report import run_silver_quality_report

if TYPE_CHECKING:
    from pyiceberg.catalog import Catalog

DEFAULT_EVENT_ANCHOR_RATE_TYPE = "DFR"


def _select_event_anchor_rate_type(
    df: pd.DataFrame, preferred: str = DEFAULT_EVENT_ANCHOR_RATE_TYPE
) -> str:
    if "rate_type" not in df.columns:
        return preferred
    available = {str(value).upper() for value in df["rate_type"].dropna().unique()}
    if preferred.upper() in available:
        return preferred.upper()
    if "MRO" in available:
        return "MRO"
    if available:
        return sorted(available)[0]
    return preferred.upper()


def transform_ecb_bronze_to_silver(
    df: pd.DataFrame,
    *,
    event_anchor_rate_type: str = DEFAULT_EVENT_ANCHOR_RATE_TYPE,
) -> pd.DataFrame:
    """Transform ECB bronze rows into cleaned silver rows."""
    transformed = df.copy()

    if "rate_type" in transformed.columns:
        anchor = _select_event_anchor_rate_type(transformed, event_anchor_rate_type)
        transformed = transformed[
            transformed["rate_type"].astype(str).str.upper() == anchor
        ]
    elif "type" in transformed.columns:
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
    transformed = transformed.drop(
        columns=["_ingestion_timestamp", "_source", "rate_type"],
        errors="ignore",
    )
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
    validate_dataset_quality(silver_df, load_contract(contract_path("fin.ecb_rates_silver")))

    overwrite_table(catalog, "silver", "ecb_rates_cleaned", silver_df, SILVER_ECB_RATES_SCHEMA)

    return {"table": "iceberg:silver.ecb_rates_cleaned", "row_count": len(silver_df)}
