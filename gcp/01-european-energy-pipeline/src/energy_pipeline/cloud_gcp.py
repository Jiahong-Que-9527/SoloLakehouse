"""Thin Google Cloud adapters for the publish ports.

Client libraries are imported lazily so the core package and its tests run
without the `cloud` extra installed. Credentials come from the environment
(Application Default Credentials locally, the job's service account in Cloud
Run). v1 semantics: raw objects are written once and never overwritten; the
window is merged on (area, metric, interval_start) inside one BigQuery job.
"""

import io

import pyarrow as pa
import pyarrow.parquet as pq

from energy_pipeline.cloud_publish import RawStore, Warehouse


class GcpRawStore(RawStore):
    """Cloud Storage adapter. Objects are new writes; existing names are never reused."""

    def __init__(self) -> None:
        self._client = None

    def _storage(self):
        if self._client is None:
            from google.cloud import storage

            self._client = storage.Client()
        return self._client

    def put_object(self, bucket: str, prefix: str, name: str, payload: bytes) -> str:
        target = self._storage().bucket(bucket).blob(f"{prefix}/{name}")
        content_type = "application/json" if name.endswith(".json") else "text/csv"
        target.upload_from_string(payload, content_type=content_type)
        return f"gs://{bucket}/{prefix}/{name}"


class GcpWarehouse(Warehouse):
    """BigQuery adapter: staging table + MERGE, then the staging table is dropped."""

    def __init__(self) -> None:
        self._client = None

    def _bigquery(self):
        if self._client is None:
            from google.cloud import bigquery

            self._client = bigquery.Client()
        return self._client

    def merge_observations(
        self,
        project: str,
        dataset: str,
        table: str,
        rows: pa.Table,
        release_id: str,
        ingested_at,
    ) -> int:
        client = self._bigquery()
        staging = f"{project}.{dataset}.{table}_staging_{release_id[:12]}"
        buffer = pa.BufferOutputStream()
        pq.write_table(rows, buffer, compression="zstd")
        from google.cloud.bigquery import LoadJobConfig, SourceFormat, WriteDisposition

        job_config = LoadJobConfig(
            source_format=SourceFormat.PARQUET, write_disposition=WriteDisposition.WRITE_TRUNCATE
        )
        client.load_table_from_file(
            io.BytesIO(buffer.getvalue().to_pybytes()), staging, job_config=job_config
        ).result()
        merge = f"""
        MERGE `{project}.{dataset}.{table}` AS target
        USING `{staging}` AS source
        ON target.area = source.area
           AND target.metric = source.metric
           AND target.interval_start = source.interval_start
        WHEN MATCHED THEN UPDATE SET
            interval_end = source.interval_end,
            value = source.value,
            unit = source.unit,
            source = source.source,
            release_id = source.release_id,
            ingested_at = source.ingested_at
        WHEN NOT MATCHED THEN INSERT ROW
        """
        client.query(merge).result()
        client.delete_table(staging, not_found_ok=True)
        return rows.num_rows

    def insert_release(self, project: str, dataset: str, record: dict) -> None:
        table = f"{project}.{dataset}.load_release"
        errors = self._bigquery().insert_rows_json(table, [record])
        if errors:
            raise OSError(f"release row rejected by {table}: {errors}")
