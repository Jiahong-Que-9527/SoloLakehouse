"""Schema contracts and file hashing helpers for D01 ECB Delta Lakehouse."""

from __future__ import annotations

import hashlib
from pathlib import Path

BRONZE_CSV_COLUMNS: tuple[str, ...] = (
    "series_key",
    "observation_date",
    "value",
    "unit",
    "title",
)

BRONZE_TABLE_COLUMNS: tuple[str, ...] = (
    *BRONZE_CSV_COLUMNS,
    "source_file",
    "source_batch_id",
    "ingested_at",
)

SILVER_TABLE_COLUMNS: tuple[str, ...] = (
    "series_key",
    "observation_date",
    "value",
    "unit",
    "frequency",
    "source_batch_id",
)

SILVER_REJECT_COLUMNS: tuple[str, ...] = (
    *BRONZE_CSV_COLUMNS,
    "source_file",
    "source_batch_id",
    "reject_reason",
)

GOLD_DAILY_COLUMNS: tuple[str, ...] = (
    "observation_date",
    "usd_per_eur",
    "policy_rate",
    "policy_rate_status",
    "policy_rate_source_date",
    "silver_version",
    "release_id",
)

GOLD_MONTHLY_VIEW_COLUMNS: tuple[str, ...] = (
    "month_utc",
    "last_fx_date",
    "last_usd_per_eur",
    "avg_usd_per_eur",
    "last_policy_rate",
    "observation_days",
)


class ContractError(ValueError):
    """Raised when an input file or pipeline invariant violates the D01 contract."""


def validate_csv_header(fieldnames: list[str] | None, path: Path) -> None:
    """Validate that a Bronze CSV header matches the exact D01 column contract."""
    if fieldnames is None or tuple(fieldnames) != BRONZE_CSV_COLUMNS:
        raise ContractError(
            f"{path.name}: expected header {list(BRONZE_CSV_COLUMNS)}, got {fieldnames!r}"
        )


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 hex digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
