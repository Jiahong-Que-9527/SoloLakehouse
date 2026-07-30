"""Runtime quality validation driven by dataset contracts."""

from __future__ import annotations

import datetime as dt

import pandas as pd

from governance.contracts import DatasetContract


def validate_dataset_quality(df: pd.DataFrame, contract: DatasetContract) -> None:
    """Raise ValueError when a dataframe violates its governed quality rules."""
    rules = contract.quality_rules
    missing = [column for column in rules.required_columns if column not in df.columns]
    if missing:
        raise ValueError(f"{contract.dataset_id}: missing required columns: {missing}")
    if len(df) < rules.min_row_count:
        raise ValueError(
            f"{contract.dataset_id}: row_count {len(df)} is below minimum {rules.min_row_count}"
        )

    null_counts = df[rules.non_null_columns].isnull().sum()
    failing_nulls = {column: int(count) for column, count in null_counts.items() if count > 0}
    if failing_nulls:
        raise ValueError(f"{contract.dataset_id}: null values found: {failing_nulls}")

    if rules.date_column is None:
        return

    dates = pd.to_datetime(df[rules.date_column], errors="coerce")
    if dates.isnull().any():
        raise ValueError(f"{contract.dataset_id}: invalid dates in {rules.date_column}")
    if rules.forbid_future_dates and (dates.dt.date > dt.date.today()).any():
        raise ValueError(f"{contract.dataset_id}: future dates found in {rules.date_column}")
    if rules.max_gap_days is not None:
        deltas = dates.sort_values().drop_duplicates().diff().dropna().dt.days
        if not deltas.empty and int(deltas.max()) > rules.max_gap_days:
            raise ValueError(
                f"{contract.dataset_id}: date gap exceeds {rules.max_gap_days} days in "
                f"{rules.date_column}"
            )
