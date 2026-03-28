"""Optional Dagster Parquet IO manager for MinIO-backed assets."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from minio import Minio

from dagster import ConfigurableIOManager, InputContext, OutputContext


class ParquetIOManager(ConfigurableIOManager):
    """Read/write pandas DataFrames as Parquet files in MinIO."""

    endpoint: str = "minio:9000"
    access_key: str = "sololakehouse"
    secret_key: str = "sololakehouse123"
    secure: bool = False
    bucket: str = "sololakehouse"
    base_prefix: str = "dagster/assets"

    def _client(self) -> Minio:
        endpoint = self.endpoint.replace("http://", "").replace("https://", "").rstrip("/")
        return Minio(
            endpoint=endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
        )

    def _path_from_asset_key(self, context: OutputContext | InputContext) -> str:
        parts = list(context.asset_key.path)
        return f"{self.base_prefix}/{'/'.join(parts)}.parquet"

    def handle_output(self, context: OutputContext, obj: Any) -> None:
        if not isinstance(obj, pd.DataFrame):
            context.log.warning("ParquetIOManager received non-DataFrame output; skipping write")
            return

        client = self._client()
        path = self._path_from_asset_key(context)
        buffer = BytesIO()
        pq.write_table(pa.Table.from_pandas(obj), buffer, compression="snappy")
        buffer.seek(0)
        client.put_object(self.bucket, path, buffer, length=buffer.getbuffer().nbytes)
        context.add_output_metadata({"parquet_path": path, "row_count": len(obj.index)})

    def load_input(self, context: InputContext) -> Any:
        client = self._client()
        path = self._path_from_asset_key(context)
        response = client.get_object(self.bucket, path)
        try:
            return pd.read_parquet(BytesIO(response.read()))
        finally:
            response.close()
            response.release_conn()
