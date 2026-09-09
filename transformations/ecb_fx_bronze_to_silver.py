"""ECB EXR FX Bronze-to-Silver transformation (panel-shaped)."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

import pandas as pd
import structlog

from governance.contracts import contract_path, load_contract
from governance.quality import validate_dataset_quality
from ingestion.iceberg_io import overwrite_table, scan_table
from ingestion.iceberg_schemas import SILVER_ECB_FX_RATES_SCHEMA
from transformations.quality_report import run_silver_quality_report

if TYPE_CHECKING:
    from pyiceberg.catalog import Catalog

logger = structlog.get_logger()

ACTIVE_CURRENCY_LOOKBACK_DAYS = 10


def _resolve_active_currencies(df: pd.DataFrame, *, lookback_days: int) -> set[str]:
    """Currencies with an observation within lookback_days of the panel max date."""
    if df.empty:
        return set()
    max_date = df["observation_date"].max()
    if isinstance(max_date, pd.Timestamp):
        max_date = max_date.date()
    cutoff = max_date - dt.timedelta(days=lookback_days)
    recent = df[df["observation_date"] >= cutoff]
    return {str(currency).upper() for currency in recent["currency"].dropna().unique()}


def transform_ecb_fx_bronze_to_silver(
    df: pd.DataFrame,
    *,
    active_lookback_days: int = ACTIVE_CURRENCY_LOOKBACK_DAYS,
) -> pd.DataFrame:
    """Deduplicate, drop inactive currencies, and compute per-currency fx_return_pct."""
    transformed = df.copy()
    transformed["observation_date"] = pd.to_datetime(
        transformed["observation_date"], errors="coerce"
    ).dt.date
    transformed["currency"] = transformed["currency"].astype(str).str.upper().str.strip()
    transformed["fx_rate"] = pd.to_numeric(transformed["fx_rate"], errors="coerce")
    transformed = transformed.dropna(subset=["observation_date", "currency", "fx_rate"])
    transformed = transformed.sort_values(["currency", "observation_date"])
    transformed = transformed.drop_duplicates(
        subset=["observation_date", "currency"], keep="last"
    )

    active = _resolve_active_currencies(transformed, lookback_days=active_lookback_days)
    logger.info(
        "ecb_fx_active_currencies_resolved",
        active_currencies=sorted(active),
        lookback_days=active_lookback_days,
    )
    transformed = transformed[transformed["currency"].isin(active)].copy()

    transformed["fx_return_pct"] = (
        transformed.groupby("currency", sort=False)["fx_rate"].pct_change(fill_method=None)
        * 100.0
    )

    transformed = transformed.drop(
        columns=["_ingestion_timestamp", "_source"],
        errors="ignore",
    )
    return transformed[["observation_date", "currency", "fx_rate", "fx_return_pct"]]


def run(catalog: "Catalog") -> dict[str, object]:
    """Read ECB FX bronze Iceberg table, transform, write to silver, return summary."""
    bronze_df = scan_table(catalog, "bronze", "ecb_fx_rates")

    if bronze_df.empty:
        raise ValueError("No ECB FX bronze records found in Iceberg table")

    silver_df = transform_ecb_fx_bronze_to_silver(bronze_df)
    run_silver_quality_report(silver_df, "ecb_fx_rates_cleaned")
    validate_dataset_quality(silver_df, load_contract(contract_path("fin.ecb_fx_rates_silver")))

    overwrite_table(
        catalog,
        "silver",
        "ecb_fx_rates_cleaned",
        silver_df,
        SILVER_ECB_FX_RATES_SCHEMA,
    )

    return {"table": "iceberg:silver.ecb_fx_rates_cleaned", "row_count": len(silver_df)}
