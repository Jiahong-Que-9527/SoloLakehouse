"""DAX Bronze-to-Silver transformation."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from transformations.quality_report import run_silver_quality_report


def transform_dax_bronze_to_silver(df: pd.DataFrame) -> pd.DataFrame:
    """Transform DAX bronze rows into cleaned silver rows."""
    transformed = df.copy()

    transformed["observation_date"] = pd.to_datetime(
        transformed["observation_date"], errors="coerce"
    ).dt.date
    for column in ["open_price", "high_price", "low_price", "close_price", "volume"]:
        transformed[column] = pd.to_numeric(transformed[column], errors="coerce")

    weekday_series = pd.to_datetime(transformed["observation_date"], errors="coerce").dt.dayofweek
    transformed = transformed[weekday_series < 5]
    transformed = transformed.sort_values("observation_date")
    transformed["daily_return"] = (
        (transformed["close_price"] / transformed["close_price"].shift(1) - 1.0) * 100
    ).round(4)
    transformed = transformed.drop_duplicates(subset=["observation_date"], keep="last")
    transformed = transformed.drop(columns=["_ingestion_timestamp", "_source"], errors="ignore")

    return transformed[
        [
            "observation_date",
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "volume",
            "daily_return",
        ]
    ]


def run(minio_client: Any, bucket: str = "sololakehouse") -> str:
    """Read DAX bronze partitions, transform, write silver parquet, and return path."""
    prefix = "bronze/dax_daily/"
    parquet_paths: list[str] = []
    for obj in minio_client.list_objects(bucket, prefix=prefix, recursive=True):
        if obj.object_name.endswith(".parquet"):
            parquet_paths.append(obj.object_name)

    if not parquet_paths:
        raise ValueError("No DAX bronze parquet partitions found")

    frames: list[pd.DataFrame] = []
    for path in parquet_paths:
        response = minio_client.get_object(bucket, path)
        try:
            frames.append(pd.read_parquet(BytesIO(response.read())))
        finally:
            response.close()
            response.release_conn()

    bronze_df = pd.concat(frames, ignore_index=True)
    silver_df = transform_dax_bronze_to_silver(bronze_df)
    run_silver_quality_report(silver_df, "dax_daily_cleaned")

    silver_path = "silver/dax_daily_cleaned/dax_daily_cleaned.parquet"
    buffer = BytesIO()
    pq.write_table(
        pa.Table.from_pandas(silver_df, preserve_index=False),
        buffer,
        compression="snappy",
    )
    buffer.seek(0)
    minio_client.put_object(bucket, silver_path, buffer, length=buffer.getbuffer().nbytes)
    return silver_path
