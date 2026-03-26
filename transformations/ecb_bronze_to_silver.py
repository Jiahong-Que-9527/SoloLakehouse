"""ECB Bronze-to-Silver transformation."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from transformations.quality_report import run_silver_quality_report


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
    transformed["rate_change_bps"] = (
        (transformed["rate_pct"] - transformed["rate_pct"].shift(1)) * 100
    ).round(1)
    transformed = transformed.drop_duplicates(subset=["observation_date"], keep="last")
    transformed = transformed.drop(columns=["_ingestion_timestamp", "_source"], errors="ignore")

    return transformed[["observation_date", "rate_pct", "rate_change_bps"]]


def run(minio_client: Any, bucket: str = "sololakehouse") -> str:
    """Read ECB bronze partitions, transform, write silver parquet, and return path."""
    prefix = "bronze/ecb_rates/"
    parquet_paths: list[str] = []
    for obj in minio_client.list_objects(bucket, prefix=prefix, recursive=True):
        if obj.object_name.endswith(".parquet"):
            parquet_paths.append(obj.object_name)

    if not parquet_paths:
        raise ValueError("No ECB bronze parquet partitions found")

    frames: list[pd.DataFrame] = []
    for path in parquet_paths:
        response = minio_client.get_object(bucket, path)
        try:
            frames.append(pd.read_parquet(BytesIO(response.read())))
        finally:
            response.close()
            response.release_conn()

    bronze_df = pd.concat(frames, ignore_index=True)
    silver_df = transform_ecb_bronze_to_silver(bronze_df)
    run_silver_quality_report(silver_df, "ecb_rates_cleaned")

    silver_path = "silver/ecb_rates_cleaned/ecb_rates_cleaned.parquet"
    buffer = BytesIO()
    pq.write_table(
        pa.Table.from_pandas(silver_df, preserve_index=False),
        buffer,
        compression="snappy",
    )
    buffer.seek(0)
    minio_client.put_object(bucket, silver_path, buffer, length=buffer.getbuffer().nbytes)
    return silver_path
