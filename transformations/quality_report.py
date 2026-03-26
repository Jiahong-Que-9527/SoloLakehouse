"""Quality reporting utilities for Silver/Gold transformations."""

from __future__ import annotations

from typing import Any

import pandas as pd
import structlog

logger = structlog.get_logger()


def run_silver_quality_report(df: pd.DataFrame, layer_name: str) -> dict[str, Any]:
    """Return quality metrics dict and log it."""
    date_column = next((col for col in df.columns if "date" in col.lower()), None)

    date_range = {"min": None, "max": None}
    if date_column is not None and not df.empty:
        date_series = pd.to_datetime(df[date_column], errors="coerce").dropna()
        if not date_series.empty:
            date_range = {
                "min": date_series.min().date().isoformat(),
                "max": date_series.max().date().isoformat(),
            }

    null_counts = {
        column: int(count)
        for column, count in df.isnull().sum().items()
        if int(count) > 0
    }

    result = {
        "layer": layer_name,
        "row_count": int(len(df)),
        "null_counts": null_counts,
        "date_range": date_range,
        "duplicate_count": int(df.duplicated().sum()),
    }
    logger.info("silver_quality_report", **result)
    return result
