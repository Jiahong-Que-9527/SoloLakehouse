"""Idempotent BigQuery raw loader (E06 · design §2/§4).

Loads the locked E01 raw layer into BigQuery ``de_raw`` through the *exact* local
pipeline that CI validates: generate the deterministic payloads, ingest them into
a throwaway DuckDB with the same ``ingestion`` code path, export each
``raw.<table>`` as Arrow, and upload with ``WRITE_TRUNCATE`` per table.

Properties this module guarantees:

- **Zero forks.** The rows uploaded are produced by ``charging_commerce.ingestion``
  (validation, quarantine, lineage columns included) — no second parser.
- **Idempotent.** Every table is replaced wholesale (``WRITE_TRUNCATE``); reruns
  converge to the same logical raw layer. Only ``_ingested_at`` reflects the
  load time (lineage, by design).
- **Free-Tier bounded.** The whole upload is asserted to stay under
  ``max_total_bytes`` (default 10 MiB, < 0.01 % of the 10 GB free storage).
- **Offline-testable.** The BigQuery client is injected; tests use a fake.

Roaming stays out of the first delivery: its payload needs the mock paginated
API server, and the models build cleanly against an empty
``raw_roaming_settlements`` (same boundary recorded in E05).
"""

from __future__ import annotations

import dataclasses
import io
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet  # noqa: F401 - registered serialization codecs for the sink

from charging_commerce import generator, ingestion

DEFAULT_MAX_TOTAL_BYTES = 10 * 1024 * 1024  # 10 MiB upload bound (design §2)
DEFAULT_BATCH_PREFIX = "e06-raw-load"

# The five locked file sources (roaming excluded, see module docstring).
FILE_SOURCES = ("bnetza", "tariffs", "sessions", "smard", "ecb")

# Tables the dbt models expect but the file loader never fills (roaming needs
# the mock API server; quarantine fills only on validation failures). Created
# empty — mirroring ingestion.ensure_schema's DuckDB behavior (E05 boundary).
SCHEMA_ONLY_TABLES: tuple[str, ...] = ("raw_roaming_settlements", "raw_quarantine")

# ingestion Column.kind -> BigQuery type (fixed schema keeps NUMERIC exact).
_KIND_TO_BQ_TYPE: dict[str, str] = {
    "varchar": "STRING",
    "timestamp": "TIMESTAMP",
    "date": "DATE",
    "int": "INT64",
}

LINEAGE_BQ_COLUMNS: tuple[tuple[str, str], ...] = (
    ("_batch_id", "STRING"),
    ("_ingested_at", "TIMESTAMP"),
    ("_source_name", "STRING"),
    ("_source_hash", "STRING"),
)

# raw_quarantine shape (ingestion.QUARANTINE_COLUMNS, mapped to BigQuery types).
_QUARANTINE_BQ_COLUMNS: tuple[tuple[str, str], ...] = (
    ("quarantine_id", "STRING"),
    ("_batch_id", "STRING"),
    ("_source_name", "STRING"),
    ("raw_payload_json", "STRING"),
    ("reject_reason", "STRING"),
    ("quarantined_at", "TIMESTAMP"),
)


@dataclass(frozen=True)
class LoadReport:
    """Result of one ``load_raw_to_bigquery`` call (logged, never uploaded raw)."""

    project: str
    dataset: str
    batch_prefix: str
    rows: dict[str, int] = field(default_factory=dict)
    job_ids: dict[str, str] = field(default_factory=dict)
    total_bytes: int = 0
    schema_only_tables: tuple[str, ...] = ()

    def summary(self) -> str:
        lines = [
            f"loaded {len(self.rows)} raw tables into "
            f"{self.project}.{self.dataset} ({self.total_bytes} bytes, "
            f"batch prefix {self.batch_prefix})"
        ]
        for table, count in sorted(self.rows.items()):
            lines.append(f"  {table}: rows={count} job={self.job_ids.get(table, '?')}")
        for table in self.schema_only_tables:
            lines.append(f"  {table}: schema-only (0 rows)")
        return "\n".join(lines)


def _payload_path(source: str, data_dir: Path, fixtures_dir: Path) -> Path:
    """Same resolution rule as the E01 CLI (generated payloads vs locked fixtures)."""
    name = ingestion.SOURCE_PAYLOADS[source]
    generated = source in ingestion.GENERATED_SOURCES
    candidate = data_dir / "generated" / name if generated else fixtures_dir / name
    if not candidate.is_file():
        raise FileNotFoundError(f"payload not found: {candidate}")
    return candidate


def _timestamp_columns(table: str) -> list[str]:
    spec = ingestion.RAW_SCHEMAS[table]
    return [column.name for column in spec.columns if column.kind == "timestamp"]


def _export_sql(table: str) -> str:
    """SELECT with UTC-tagged timestamps so Arrow carries tz-aware TIMESTAMP data."""
    spec = ingestion.RAW_SCHEMAS[table]
    selected = [
        f"{column.name} at time zone 'UTC' as {column.name}"
        if column.kind == "timestamp"
        else column.name
        for column in spec.columns
    ]
    for name in ingestion.LINEAGE_COLUMNS:
        if name == "_ingested_at":
            selected.append(f"{name} at time zone 'UTC' as {name}")
        else:
            selected.append(name)
    return f"select {', '.join(selected)} from raw.{table}"


def build_raw_payloads(
    fixtures_dir: Path,
    seed: int = 42,
    work_dir: Path | None = None,
) -> dict[str, tuple]:
    """Generate + ingest the five file sources and return ``table -> (rows, nbytes)``.

    The returned values are Arrow tables (via DuckDB), ready for upload. The
    helper keeps a temp directory only when ``work_dir`` is given.
    """
    import duckdb  # local import: keeps the module importable without the wheel path

    fixtures_dir = Path(fixtures_dir)
    temp = None
    if work_dir is None:
        temp = tempfile.TemporaryDirectory(prefix="e06-bq-loader-")
        work_dir = Path(temp.name)
    else:
        work_dir = Path(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)

    try:
        data_dir = work_dir / "data"
        state_dir = work_dir / "state"
        db_path = work_dir / "warehouse.duckdb"

        # generator.generate() writes payloads directly into the directory given
        # (same convention as `charging-commerce generate --out-dir`).
        generator.generate(data_dir / "generated", fixtures_dir, seed=seed)

        for source in FILE_SOURCES:
            payload = _payload_path(source, data_dir, fixtures_dir)
            batch_id = f"{DEFAULT_BATCH_PREFIX}-{source}"
            ingestion.ingest_file(source, payload, batch_id, db_path, state_dir)

        exported: dict[str, tuple] = {}
        conn = duckdb.connect(str(db_path), read_only=True)
        try:
            # Force UTC so Arrow exports carry tz=UTC instants for BigQuery TIMESTAMP.
            conn.execute("set timezone = 'UTC'")
            for source in FILE_SOURCES:
                table = ingestion.SOURCE_TABLES[source]
                arrow_table = conn.sql(_export_sql(table)).to_arrow_table()
                exported[table] = (arrow_table, arrow_table.nbytes)
        finally:
            conn.close()
        return exported
    finally:
        if temp is not None:
            temp.cleanup()


def bq_schema(table: str) -> list:
    """BigQuery ``SchemaField`` list for one raw table (models + lineage).

    Decimals are declared as plain ``NUMERIC``: load jobs reject parameterized
    ``NUMERIC(p,s)`` strings, and the Parquet payload carries the exact
    decimal128(p,s) of the contract columns, so precision/scale survive the load.
    """
    from google.cloud import bigquery

    spec = ingestion.RAW_SCHEMAS[table]
    fields: list = []
    for column in spec.columns:
        bq_type = "NUMERIC" if column.kind.startswith("decimal") else _KIND_TO_BQ_TYPE[column.kind]
        fields.append(bigquery.SchemaField(column.name, bq_type, mode="NULLABLE"))
    fields.extend(
        bigquery.SchemaField(name, bq_type, mode="NULLABLE") for name, bq_type in LINEAGE_BQ_COLUMNS
    )
    return fields


def load_raw_to_bigquery(
    client,
    fixtures_dir: Path,
    dataset: str = "de_raw",
    seed: int = 42,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
    batch_prefix: str = DEFAULT_BATCH_PREFIX,
    work_dir: Path | None = None,
    started_at: datetime | None = None,
) -> LoadReport:
    """Upload the five locked raw sources into ``<project>.<dataset>`` idempotently.

    ``client`` is a ``google.cloud.bigquery.Client`` (or a test double providing
    ``load_table_from_file`` and ``project``).
    """
    from google.cloud import bigquery

    started_at = started_at or datetime.now(UTC).replace(tzinfo=None)
    exported = build_raw_payloads(fixtures_dir, seed=seed, work_dir=work_dir)

    total_bytes = sum(nbytes for _, nbytes in exported.values())
    if total_bytes > max_total_bytes:
        raise ValueError(
            f"raw upload is {total_bytes} bytes, above the {max_total_bytes}-byte "
            "Free-Tier guard; raise max_total_bytes deliberately if this is expected"
        )

    project = client.project
    report = LoadReport(
        project=project,
        dataset=dataset,
        batch_prefix=batch_prefix,
        total_bytes=total_bytes,
    )
    for source in FILE_SOURCES:
        table_id = ingestion.SOURCE_TABLES[source]
        arrow_table, _ = exported[table_id]
        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            schema=bq_schema(table_id),
            source_format=bigquery.SourceFormat.PARQUET,
        )
        destination = f"{project}.{dataset}.{table_id}"
        sink = io.BytesIO()
        pyarrow.parquet.write_table(arrow_table, sink)
        sink.seek(0)
        job = client.load_table_from_file(sink, destination, job_config=job_config)
        job.result()
        report.rows[table_id] = arrow_table.num_rows
        report.job_ids[table_id] = getattr(job, "job_id", "unknown")

    created = _ensure_schema_only_tables(client, project, dataset)
    return dataclasses.replace(report, schema_only_tables=created)


def _ensure_schema_only_tables(client, project: str, dataset: str) -> tuple[str, ...]:
    """Create the never-filled raw tables as empty, if missing (E05 boundary)."""
    from google.cloud import bigquery
    from google.cloud.exceptions import NotFound

    created: list[str] = []
    for table_id in SCHEMA_ONLY_TABLES:
        destination = f"{project}.{dataset}.{table_id}"
        try:
            client.get_table(destination)
        except NotFound:
            client.create_table(
                bigquery.Table(destination, schema=bq_schema_from_lineage(table_id))
            )
            created.append(table_id)
    return tuple(created)


def bq_schema_from_lineage(table_id: str) -> list:
    """``SchemaField`` list for the schema-only tables (contract + lineage shape).

    ``raw_roaming_settlements`` carries the full contract schema plus the
    lineage columns (exactly as ``ingestion.ensure_schema`` creates it on
    DuckDB); ``raw_quarantine`` keeps its quarantine payload columns.
    """
    from google.cloud import bigquery

    if table_id == "raw_quarantine":
        fields = [
            bigquery.SchemaField(name, bq_type, mode="NULLABLE")
            for name, bq_type in _QUARANTINE_BQ_COLUMNS
        ]
        return fields
    return bq_schema(table_id)
