"""Thin BigQuery adapters for the publication path (G03 pattern).

Client libraries are imported lazily so the core package and its tests
run without the `cloud` extra. The producer identity reads the G01 input
release, the gate runs client-side, and the publication primitives issue
DDL/DML statements whose shapes the tests pin structurally:

- the version table is created once from the gated rows and never mutated;
- the `_current` authorised view is one CREATE OR REPLACE VIEW statement;
- the release row, quarantine rows and the manifest are plain inserts;
- withdraw repoints the view at the previous passed release, or at an
  empty view over the withdrawn table's schema.
"""

from datetime import datetime

from energy_product.store import ReleaseRow


class BigQueryProductStore:
    """Runs the publication primitives against the `energy_product` dataset."""

    def __init__(self, dataset: str, *, client=None) -> None:
        self._dataset = dataset
        self._client = client

    def _bigquery(self):
        if self._client is None:
            from google.cloud import bigquery

            self._client = bigquery.Client()
        return self._client

    def _table(self, project: str, name: str) -> str:
        return f"{project}.{self._dataset}.{name}"

    def fetch_input_release(self, project: str, input_release_id: str) -> tuple[dict, list[dict]]:
        """The G01 ledger row and its observation rows (producer grant)."""
        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter

        client = self._bigquery()
        ledger_sql = (
            f"SELECT release_id, window_start, window_end, input_checksum, row_count, git_sha, "
            f"quality_status, published_at FROM `{project}.energy.load_release` "
            f"WHERE release_id = @release_id"
        )
        rows_sql = (
            f"SELECT interval_start, interval_end, area, metric, value, unit, release_id, "
            f"ingested_at FROM `{project}.energy.metric_observation` "
            f"WHERE release_id = @release_id ORDER BY interval_start"
        )
        config = QueryJobConfig(
            query_parameters=[ScalarQueryParameter("release_id", "STRING", input_release_id)]
        )
        ledger = [dict(row) for row in client.query(ledger_sql, job_config=config).result()]
        if len(ledger) != 1:
            raise LookupError(f"input release {input_release_id!r} not found in the G01 ledger")
        rows = [dict(row) for row in client.query(rows_sql, job_config=config).result()]
        return ledger[0], rows

    def fetch_release_rows(self, product: str, release_id: str) -> list[dict]:
        client = self._bigquery()
        sql = (
            f"SELECT * FROM `{self._table(client.project, 'release')}` "
            f"WHERE product = @product AND release_id = @release_id"
        )
        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter

        config = QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("product", "STRING", product),
                ScalarQueryParameter("release_id", "STRING", release_id),
            ]
        )
        return [dict(row) for row in client.query(sql, job_config=config).result()]

    def version_table_exists(self, product: str, release_id: str) -> bool:
        client = self._bigquery()
        from google.cloud.bigquery import NotFound

        try:
            client.get_table(self._table(client.project, f"{product}_v{release_id}"))
            return True
        except NotFound:
            return False

    def write_version_table(
        self, project: str, product: str, release_id: str, rows: list[dict]
    ) -> None:
        from google.cloud.bigquery import LoadJobConfig, SourceFormat, WriteDisposition

        client = self._bigquery()
        job_config = LoadJobConfig(
            source_format=SourceFormat.PARQUET, write_disposition=WriteDisposition.WRITE_EMPTY
        )
        buffer = _rows_to_parquet(rows)
        client.load_table_from_file(
            buffer, self._table(client.project, f"{product}_v{release_id}"), job_config=job_config
        ).result()

    def point_current_view(self, project: str, product: str, release_id: str) -> None:
        client = self._bigquery()
        slug = product.replace("-", "_")
        sql = (
            f"CREATE OR REPLACE VIEW `{self._table(client.project, f'{slug}_current')}` AS "
            f"SELECT * FROM `{self._table(client.project, f'{slug}_v{release_id}')}`"
        )
        client.query(sql).result()

    def empty_current_view(self, project: str, product: str, schema_table: str) -> None:
        client = self._bigquery()
        slug = product.replace("-", "_")
        sql = (
            f"CREATE OR REPLACE VIEW `{self._table(client.project, f'{slug}_current')}` AS "
            f"SELECT * FROM `{self._table(client.project, schema_table)}` WHERE FALSE"
        )
        client.query(sql).result()

    def insert_release_row(self, project: str, row: ReleaseRow) -> None:
        client = self._bigquery()
        errors = client.insert_rows_json(
            self._table(client.project, "release"),
            [
                {
                    "product": row.product,
                    "release_id": row.release_id,
                    "input_release_id": row.input_release_id,
                    "contract_version": row.contract_version,
                    "status": row.status,
                    "output_table": row.output_table,
                    "git_sha": row.git_sha,
                    "approver": row.approver,
                    "checksum": row.checksum,
                    "published_at": _stamp(row.published_at),
                    "manifest": _manifest_json(row.manifest),
                }
            ],
        )
        if errors:
            raise OSError(f"release row rejected by the ledger: {errors}")

    def mark_release_status(self, project: str, product: str, release_id: str, status: str) -> None:
        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter

        client = self._bigquery()
        sql = (
            f"UPDATE `{self._table(client.project, 'release')}` SET status = @status "
            f"WHERE product = @product AND release_id = @release_id"
        )
        config = QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("status", "STRING", status),
                ScalarQueryParameter("product", "STRING", product),
                ScalarQueryParameter("release_id", "STRING", release_id),
            ]
        )
        client.query(sql, job_config=config).result()

    def insert_quarantine_rows(self, project: str, rows: list[dict]) -> None:
        client = self._bigquery()
        payload = [
            {
                "product": row["product"],
                "release_id": row["release_id"],
                "input_release_id": row["input_release_id"],
                "check": row["check"],
                "detail": row["detail"],
                "offending": _offending_json(row["offending"]),
                "recorded_at": _stamp(row["recorded_at"]),
            }
            for row in rows
        ]
        errors = client.insert_rows_json(self._table(client.project, "quarantine"), payload)
        if errors:
            raise OSError(f"quarantine rows rejected: {errors}")


def _rows_to_parquet(rows: list[dict]):
    import io

    import pyarrow as pa
    import pyarrow.parquet as pq

    if not rows:
        raise ValueError("cannot write an empty version table")
    table = pa.Table.from_pylist(rows)
    buffer = io.BytesIO()
    pq.write_table(table, buffer, compression="zstd")
    buffer.seek(0)
    return buffer


def _stamp(value: datetime) -> str:
    return value.astimezone(value.tzinfo or datetime.now().astimezone().tzinfo).isoformat()


def _manifest_json(manifest: dict) -> str:
    import json

    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), default=str)


def _offending_json(offending) -> str:
    import json

    return json.dumps([list(key) for key in offending[:20]], default=str)
