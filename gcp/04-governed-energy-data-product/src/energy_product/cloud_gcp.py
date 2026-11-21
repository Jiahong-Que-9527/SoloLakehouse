"""Thin BigQuery adapters for the publication path (G03 pattern).

``BigQueryProductStore`` implements the SAME store port the local
``InMemoryProductStore`` satisfies, so ``publisher.publish`` and
``publisher.withdraw`` run unchanged against BigQuery. Mapping decisions:

- the ``_current`` authorised view IS the current pointer; its definition
  in INFORMATION_SCHEMA.VIEWS names the version table it selects from;
- an empty authorised view uses the typed zero-row placeholder (no
  version-table reference), so a withdrawn product reads as "no current";
- the version table's description carries the rows checksum, which makes
  the crash-between-table-and-view window checksum-verifiable on retry;
- the release row's ``manifest`` column is the manifest's durable home,
  so ``record_manifest`` is a deliberate no-op here;
- client libraries are imported lazily; credentials come from the
  environment (the producer SA in Cloud Run, ADC locally).
"""

import json
import re
from datetime import UTC, datetime

from energy_product.store import ReleaseRow


class BigQueryProductStore:
    """Publication primitives against the ``energy_product`` dataset."""

    def __init__(self, dataset: str, *, client=None) -> None:
        self._dataset = dataset
        self._client = client

    def _bigquery(self):
        if self._client is None:
            from google.cloud import bigquery

            self._client = bigquery.Client()
        return self._client

    def _table(self, name: str) -> str:
        return f"{self._bigquery().project}.{self._dataset}.{name}"

    # --- producer-side read of the G01 input ---------------------------------

    def fetch_input_release(self, input_release_id: str) -> tuple[dict, list[dict]]:
        """The G01 ledger row and its observation rows (producer grant)."""
        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter

        client = self._bigquery()
        project = client.project
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

    # --- the store port -------------------------------------------------------

    def release_row(self, product: str, release_id: str) -> ReleaseRow | None:
        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter

        client = self._bigquery()
        sql = (
            f"SELECT * FROM `{self._table('release')}` "
            f"WHERE product = @product AND release_id = @release_id"
        )
        config = QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("product", "STRING", product),
                ScalarQueryParameter("release_id", "STRING", release_id),
            ]
        )
        rows = [dict(row) for row in client.query(sql, job_config=config).result()]
        if not rows:
            return None
        row = rows[0]
        return ReleaseRow(
            product=row["product"],
            release_id=row["release_id"],
            input_release_id=row["input_release_id"],
            contract_version=row["contract_version"],
            status=row["status"],
            output_table=row["output_table"],
            git_sha=row.get("git_sha"),
            approver=row["approver"],
            checksum=row["checksum"],
            published_at=row["published_at"],
            manifest=json.loads(row["manifest"]),
        )

    def releases(self, product: str) -> tuple[ReleaseRow, ...]:
        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter

        client = self._bigquery()
        sql = (
            f"SELECT * FROM `{self._table('release')}` WHERE product = @product "
            f"ORDER BY published_at"
        )
        config = QueryJobConfig(
            query_parameters=[ScalarQueryParameter("product", "STRING", product)]
        )
        return [
            self.release_row(product, dict(row)["release_id"])
            for row in client.query(sql, job_config=config).result()
        ]

    def recorded_checksum(self, product: str, release_id: str) -> str | None:
        """The checksum travels in the version table's description, so it is
        verbable before the ledger row exists (the crash window)."""
        from google.cloud import bigquery

        client = self._bigquery()
        try:
            table = client.get_table(self._table(f"{product}_v{release_id}"))
        except bigquery.NotFound:
            return None
        return table.description or None

    def current_release_id(self, product: str) -> str | None:
        """Parse the pointer out of the current view's definition."""
        client = self._bigquery()
        sql = (
            f"SELECT view_definition FROM `{client.project}.{self._dataset}"
            f".INFORMATION_SCHEMA.VIEWS` WHERE table_name = '{product}_current'"
        )
        rows = [dict(row) for row in client.query(sql).result()]
        if not rows:
            return None
        match = re.search(rf"{re.escape(product)}_v([^`']+)", rows[0]["view_definition"])
        return match.group(1) if match else None

    def current_rows(self, product: str) -> list[dict]:
        client = self._bigquery()
        sql = f"SELECT * FROM `{self._table(f'{product}_current')}`"
        return [dict(row) for row in client.query(sql).result()]

    def version_rows(self, product: str, release_id: str) -> list[dict]:
        client = self._bigquery()
        sql = f"SELECT * FROM `{self._table(f'{product}_v{release_id}')}`"
        return [dict(row) for row in client.query(sql).result()]

    def write_version_table(
        self, product: str, release_id: str, rows: list[dict], checksum: str
    ) -> None:
        from google.cloud.bigquery import LoadJobConfig, SourceFormat, WriteDisposition

        client = self._bigquery()
        job_config = LoadJobConfig(
            source_format=SourceFormat.PARQUET, write_disposition=WriteDisposition.WRITE_EMPTY
        )
        destination = self._table(f"{product}_v{release_id}")
        client.load_table_from_file(
            _rows_to_parquet(rows), destination, job_config=job_config
        ).result()
        table = client.get_table(destination)
        table.description = checksum
        client.update_table(table, ["description"])

    def point_current_view(self, product: str, release_id: str) -> None:
        client = self._bigquery()
        sql = (
            f"CREATE OR REPLACE VIEW `{self._table(f'{product}_current')}` AS "
            f"SELECT * FROM `{self._table(f'{product}_v{release_id}')}`"
        )
        client.query(sql).result()

    def empty_current_view(self, product: str, schema_table: str) -> None:
        """The typed zero-row placeholder: schema preserved, no rows, and no
        version-table reference so the pointer reads as empty."""
        client = self._bigquery()
        sql = (
            f"CREATE OR REPLACE VIEW `{self._table(f'{product}_current')}` AS "
            f"SELECT * FROM `{self._table(schema_table)}` WHERE FALSE"
        )
        client.query(sql).result()

    def insert_release_row(self, row: ReleaseRow) -> None:
        client = self._bigquery()
        errors = client.insert_rows_json(
            self._table("release"),
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
                    "manifest": json.dumps(
                        row.manifest, sort_keys=True, separators=(",", ":"), default=str
                    ),
                }
            ],
        )
        if errors:
            raise OSError(f"release row rejected by the ledger: {errors}")

    def mark_release_status(self, product: str, release_id: str, status: str) -> None:
        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter

        client = self._bigquery()
        sql = (
            f"UPDATE `{self._table('release')}` SET status = @status "
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

    def insert_quarantine_rows(self, rows: list[dict]) -> None:
        client = self._bigquery()
        payload = [
            {
                "product": row["product"],
                "release_id": row["release_id"],
                "input_release_id": row["input_release_id"],
                "check": row["check"],
                "detail": row["detail"],
                "offending": json.dumps([list(key) for key in row["offending"][:20]], default=str),
                "recorded_at": _stamp(row["recorded_at"]),
            }
            for row in rows
        ]
        errors = client.insert_rows_json(self._table("quarantine"), payload)
        if errors:
            raise OSError(f"quarantine rows rejected: {errors}")

    def record_manifest(self, manifest: dict) -> None:
        """No-op by design: the release row's manifest column is the durable
        home, written in the same commit that marks the release passed."""


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
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()
