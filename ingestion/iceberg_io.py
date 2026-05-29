"""PyIceberg I/O helpers for the SoloLakehouse medallion layers.

All pipeline writes go through `append_table` (Bronze) or `overwrite_table`
(Silver / Gold).  `scan_table` is used by transformations and freshness checks.
Callers inject a `Catalog` so tests can pass a mock without touching
Hive Metastore or MinIO.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import pandas as pd
import pyarrow as pa
import structlog

if TYPE_CHECKING:
    from pyiceberg.catalog import Catalog
    from pyiceberg.partitioning import PartitionSpec
    from pyiceberg.schema import Schema

logger = structlog.get_logger()


def _downcast_ns_timestamps(table: pa.Table) -> pa.Table:
    """Cast nanosecond-precision timestamp columns to microseconds.

    Iceberg v1/v2 only supports microsecond (us) timestamp precision.
    Python 3.11+ datetime.now() returns ns-precision via pandas, so we must
    downcast before handing to pyiceberg.
    """
    new_fields = []
    needs_cast = False
    for field in table.schema:
        if pa.types.is_timestamp(field.type) and field.type.unit == "ns":
            new_fields.append(field.with_type(pa.timestamp("us", tz=field.type.tz)))
            needs_cast = True
        else:
            new_fields.append(field)
    if not needs_cast:
        return table
    return table.cast(pa.schema(new_fields))


def get_catalog(
    name: str = "hive",
    uri: str | None = None,
    warehouse: str | None = None,
    s3_endpoint: str | None = None,
    access_key: str | None = None,
    secret_key: str | None = None,
) -> "Catalog":
    """Create a HiveCatalog backed by Hive Metastore and MinIO (S3-compatible).

    All parameters fall back to environment variables so Docker and local-dev
    environments work without extra configuration.
    """
    from pyiceberg.catalog.hive import HiveCatalog

    minio_ep = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    data_bucket = os.environ.get("DATA_BUCKET", os.environ.get("BUCKET_NAME", "sololakehouse"))
    # WAREHOUSE_URI is s3a:// for Hadoop; pyiceberg uses s3://
    raw_warehouse = os.environ.get("WAREHOUSE_URI", f"s3://{data_bucket}/warehouse/")
    effective_warehouse = raw_warehouse.replace("s3a://", "s3://")

    props: dict[str, str] = {
        "uri": uri or os.environ.get("HIVE_METASTORE_URI", "thrift://localhost:9083"),
        "warehouse": warehouse or effective_warehouse,
        "s3.endpoint": s3_endpoint or f"http://{minio_ep}",
        "s3.access-key-id": access_key or os.environ.get("S3_ACCESS_KEY", "sololakehouse"),
        "s3.secret-access-key": secret_key or os.environ.get("S3_SECRET_KEY", "sololakehouse123"),
        "s3.path-style-access": "true",
    }
    return HiveCatalog(name, **props)


# ── namespace helpers ─────────────────────────────────────────────────────────


def ensure_namespace(catalog: "Catalog", namespace: str) -> None:
    """Create namespace if it does not already exist (idempotent)."""
    from pyiceberg.exceptions import NamespaceAlreadyExistsError

    try:
        catalog.create_namespace(namespace)
        logger.info("iceberg_namespace_created", namespace=namespace)
    except NamespaceAlreadyExistsError:
        pass


# ── internal helpers ──────────────────────────────────────────────────────────


def _get_or_create_table(
    catalog: "Catalog",
    namespace: str,
    table_name: str,
    schema: "Schema",
    partition_spec: "PartitionSpec | None",
) -> Any:
    from pyiceberg.exceptions import NoSuchTableError
    from pyiceberg.partitioning import PartitionSpec as PS

    identifier = (namespace, table_name)
    try:
        return catalog.load_table(identifier)
    except NoSuchTableError:
        ensure_namespace(catalog, namespace)
        return catalog.create_table(
            identifier=identifier,
            schema=schema,
            partition_spec=partition_spec or PS(),
        )


# ── public write API ──────────────────────────────────────────────────────────


def append_table(
    catalog: "Catalog",
    namespace: str,
    table_name: str,
    df: pd.DataFrame,
    schema: "Schema",
    partition_spec: "PartitionSpec | None" = None,
) -> None:
    """Append *df* to an Iceberg table, creating it if needed (Bronze pattern)."""
    tbl = _get_or_create_table(catalog, namespace, table_name, schema, partition_spec)
    arrow_table = _downcast_ns_timestamps(pa.Table.from_pandas(df, preserve_index=False))
    tbl.append(arrow_table)
    logger.info("iceberg_appended", table=f"{namespace}.{table_name}", rows=len(df))


def overwrite_table(
    catalog: "Catalog",
    namespace: str,
    table_name: str,
    df: pd.DataFrame,
    schema: "Schema",
    partition_spec: "PartitionSpec | None" = None,
) -> None:
    """Replace all rows in an Iceberg table (Silver / Gold pattern)."""
    tbl = _get_or_create_table(catalog, namespace, table_name, schema, partition_spec)
    arrow_table = _downcast_ns_timestamps(pa.Table.from_pandas(df, preserve_index=False))
    tbl.overwrite(arrow_table)
    logger.info("iceberg_overwritten", table=f"{namespace}.{table_name}", rows=len(df))


# ── public read API ───────────────────────────────────────────────────────────


def scan_table(
    catalog: "Catalog",
    namespace: str,
    table_name: str,
) -> pd.DataFrame:
    """Scan an entire Iceberg table and return as a pandas DataFrame."""
    tbl = catalog.load_table((namespace, table_name))
    return tbl.scan().to_pandas()
