"""Bronze-layer Parquet writer for MinIO."""

from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


class BronzeWriter:
    def __init__(self, minio_client: Any, bucket: str = "sololakehouse"):
        self.minio = minio_client
        self.bucket = bucket

    def write(self, df: pd.DataFrame, source: str, ingestion_date: str | None = None) -> str:
        """Write dataframe as snappy parquet and return object path."""
        partition_date = ingestion_date or date.today().isoformat()
        path = f"bronze/{source}/ingestion_date={partition_date}/{source}.parquet"

        buffer = BytesIO()
        table = pa.Table.from_pandas(df, preserve_index=False)
        pq.write_table(table, buffer, compression="snappy")
        buffer.seek(0)

        self.minio.put_object(
            self.bucket,
            path,
            buffer,
            length=buffer.getbuffer().nbytes,
        )
        return path

    def write_rejected(
        self,
        records: list[dict[str, Any]],
        source: str,
        ingestion_date: str | None = None,
    ) -> str | None:
        """Write rejected records parquet and return object path."""
        if not records:
            return None

        for record in records:
            reason = record.get("rejection_reason")
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError("Each rejected record must include a non-empty rejection_reason")

        partition_date = ingestion_date or date.today().isoformat()
        path = (
            f"bronze/rejected/source={source}/"
            f"ingestion_date={partition_date}/rejected.parquet"
        )
        rejected_df = pd.DataFrame(records)

        buffer = BytesIO()
        table = pa.Table.from_pandas(rejected_df, preserve_index=False)
        pq.write_table(table, buffer, compression="snappy")
        buffer.seek(0)

        self.minio.put_object(
            self.bucket,
            path,
            buffer,
            length=buffer.getbuffer().nbytes,
        )
        return path
