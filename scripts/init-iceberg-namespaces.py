#!/usr/bin/env python3
"""Idempotent bootstrap script: create Iceberg namespaces and tables.

Run once after `make up` (or whenever the Hive Metastore is reset).
Safe to re-run — existing namespaces and tables are left untouched.

Usage:
    python scripts/init-iceberg-namespaces.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import structlog
from pyiceberg.exceptions import TableAlreadyExistsError
from pyiceberg.partitioning import PartitionSpec

# Allow running from the project root without installing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_dotenv() -> None:
    """Load .env from the repo root if present (same logic as verify-demo.py)."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

logger = structlog.get_logger()


def main() -> None:
    from ingestion.iceberg_io import ensure_namespace, get_catalog
    from ingestion.iceberg_schemas import (
        BRONZE_DAX_DAILY_PARTITION,
        BRONZE_DAX_DAILY_SCHEMA,
        BRONZE_ECB_RATES_PARTITION,
        BRONZE_ECB_RATES_SCHEMA,
        BRONZE_REJECTED_SCHEMA,
        GOLD_FEATURES_SCHEMA,
        SILVER_DAX_DAILY_SCHEMA,
        SILVER_ECB_RATES_SCHEMA,
    )

    tables = [
        # (namespace, table_name, schema, partition_spec)
        ("bronze", "ecb_rates", BRONZE_ECB_RATES_SCHEMA, BRONZE_ECB_RATES_PARTITION),
        ("bronze", "dax_daily", BRONZE_DAX_DAILY_SCHEMA, BRONZE_DAX_DAILY_PARTITION),
        ("bronze", "rejected_records", BRONZE_REJECTED_SCHEMA, None),
        ("silver", "ecb_rates_cleaned", SILVER_ECB_RATES_SCHEMA, None),
        ("silver", "dax_daily_cleaned", SILVER_DAX_DAILY_SCHEMA, None),
        ("gold", "ecb_dax_features", GOLD_FEATURES_SCHEMA, None),
    ]

    catalog = get_catalog()
    logger.info("iceberg_init_started")

    for ns in ["bronze", "silver", "gold"]:
        ensure_namespace(catalog, ns)

    for namespace, table_name, schema, partition_spec in tables:
        identifier = (namespace, table_name)
        try:
            catalog.create_table(
                identifier=identifier,
                schema=schema,
                partition_spec=partition_spec or PartitionSpec(),
            )
            logger.info("iceberg_table_created", table=f"{namespace}.{table_name}")
        except TableAlreadyExistsError:
            logger.info("iceberg_table_exists", table=f"{namespace}.{table_name}")

    logger.info("iceberg_init_complete")


if __name__ == "__main__":
    main()
