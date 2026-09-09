"""Runtime quality validation driven by dataset contracts."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pandas as pd

from governance.contracts import DatasetContract


def validate_dataset_quality(df: pd.DataFrame, contract: DatasetContract) -> None:
    """Raise ValueError when a dataframe violates its governed quality rules.

    Continuity (`max_gap_days`) is enforced here as a write gate. Freshness
    (`max_staleness_days`) is intentionally not — it is evaluated separately as a
    Dagster WARN asset check so a source outage does not block Gold rebuilds.
    """
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


def evaluate_max_staleness(
    df: pd.DataFrame,
    contract: DatasetContract,
    *,
    as_of: dt.date | None = None,
) -> tuple[bool, str, dict[str, Any]]:
    """Return (passed, description, metadata) for the contract's freshness SLA.

    Datasets without ``max_staleness_days`` always pass. Empty frames fail when a
    staleness rule is configured.
    """
    rules = contract.quality_rules
    if rules.max_staleness_days is None or rules.date_column is None:
        return True, f"{contract.dataset_id}: no max_staleness_days configured", {}

    as_of_date = as_of or dt.date.today()
    if df.empty or rules.date_column not in df.columns:
        return (
            False,
            f"{contract.dataset_id}: empty or missing {rules.date_column} for staleness check",
            {"as_of": as_of_date.isoformat(), "max_staleness_days": rules.max_staleness_days},
        )

    dates = pd.to_datetime(df[rules.date_column], errors="coerce").dropna()
    if dates.empty:
        return (
            False,
            f"{contract.dataset_id}: no valid dates in {rules.date_column}",
            {"as_of": as_of_date.isoformat(), "max_staleness_days": rules.max_staleness_days},
        )

    newest = dates.max().date()
    age_days = (as_of_date - newest).days
    passed = age_days <= rules.max_staleness_days
    metadata: dict[str, Any] = {
        "as_of": as_of_date.isoformat(),
        "newest_observation_date": newest.isoformat(),
        "age_days": age_days,
        "max_staleness_days": rules.max_staleness_days,
        "update_pattern": rules.update_pattern,
    }
    description = (
        f"{contract.dataset_id}: newest row is {age_days} day(s) old "
        f"(limit {rules.max_staleness_days})"
    )
    return passed, description, metadata
