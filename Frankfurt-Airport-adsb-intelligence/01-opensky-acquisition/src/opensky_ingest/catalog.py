"""Lakehouse helpers (M4) and the dataset summary (M5).

`export_manifests` writes the manifest Parquet tables and the dataset
contract. `build_catalog` creates the DuckDB catalog with views over the
Bronze files, driven by the manifests. `dataset_summary` aggregates the
whole dataset, including the distinct aircraft counts, which need DuckDB.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from . import __version__
from .batch import load_batches
from .config import Config, ConfigError
from .fetch import git_commit, new_run_id
from .reference import hour_epoch_label, load_epochs, load_gaps
from .schema import FLIGHT_COLUMNS, STATE_VECTOR_COLUMNS
from .state import append_event
from .util import iso, utc_now, write_json_atomic

DATASETS_DIR = "metadata/datasets"
HOUR_MANIFEST_PARQUET = "hour_manifest.parquet"
FLIGHT_MANIFEST_PARQUET = "flight_manifest.parquet"
BATCH_MANIFEST_PARQUET = "batch_manifest.parquet"
CONTRACT_NAME = "eddf_r75km_v1.json"
SUMMARY_NAME = "dataset_summary.json"
CATALOG_NAME = "catalog.duckdb"


# ---------------------------------------------------------------------------
# Export


def export_manifests(cfg: Config, *, now: datetime | None = None) -> dict[str, Any]:
    """Write the three manifest Parquet tables and the dataset contract.

    The Parquet files carry absolute paths so lineage queries join straight
    to the data. A repeat run rewrites the same files.
    """
    root = cfg.paths.data_root
    moment = now or utc_now()
    batch_of_hour, batch_of_day = _batch_index()
    batches = load_batches()

    hour_rows = _index_rows(root, "hours", "hour")
    hour_rows = [_hour_row(row, batch_of_hour, cfg) for row in hour_rows]
    flight_rows = _index_rows(root, "flight_days", "day")
    flight_rows = [_flight_row(row, batch_of_day, cfg) for row in flight_rows]
    batch_rows = _batch_rows(root, batches)

    out = root / DATASETS_DIR
    out.mkdir(parents=True, exist_ok=True)
    _write_table(out / HOUR_MANIFEST_PARQUET, hour_rows, HOUR_SCHEMA)
    _write_table(out / FLIGHT_MANIFEST_PARQUET, flight_rows, FLIGHT_SCHEMA)
    _write_table(out / BATCH_MANIFEST_PARQUET, batch_rows, BATCH_SCHEMA)
    contract = dataset_contract(cfg, now=moment)
    write_json_atomic(out / CONTRACT_NAME, contract)
    record = {
        "batches": len(batch_rows),
        "contract": str(out / CONTRACT_NAME),
        "flight_days": len(flight_rows),
        "hours": len(hour_rows),
        "run_id": new_run_id(moment),
        "tool_version": __version__,
        "written_at": iso(moment),
    }
    append_event(
        root,
        {
            "at": iso(moment),
            "kind": "manifests_exported",
            **{k: record[k] for k in ("hours", "flight_days", "batches")},
        },
    )
    return record


def dataset_contract(cfg: Config, *, now: datetime | None = None) -> dict[str, Any]:
    """The dataset contract: bounds, SQL templates, schema, gaps and epochs."""
    box = cfg.region.bbox
    columns = ", ".join(STATE_VECTOR_COLUMNS)
    flight_columns = ", ".join(FLIGHT_COLUMNS)
    gaps = load_gaps()
    epochs = load_epochs()
    return {
        "dataset_id": cfg.region.id,
        "version": cfg.region.version,
        "airport": cfg.region.airport,
        "center": {"latitude": cfg.region.latitude, "longitude": cfg.region.longitude},
        "radius_km": cfg.region.radius_km,
        "bbox": {
            "south": box.south,
            "north": box.north,
            "west": box.west,
            "east": box.east,
        },
        "period": {
            "start": cfg.period.start.isoformat(),
            "end": cfg.period.end.isoformat(),
            "hours": cfg.period.hours,
            "flight_days": cfg.period.days + 1,
        },
        "source": {
            "host": cfg.source.host,
            "port": cfg.source.port,
            "state_vectors_table": cfg.source.table(cfg.state_vectors.table),
            "flights_table": cfg.source.table(cfg.flights.table),
        },
        "sql_templates": {
            "state_vectors": (
                f"SELECT {columns} FROM {cfg.source.table(cfg.state_vectors.table)} "
                "WHERE hour = {hour_epoch} "
                f"AND lat BETWEEN {{south}} AND {{north}} "
                f"AND lon BETWEEN {{west}} AND {{east}}"
            ),
            "flights": (
                f"SELECT {flight_columns} FROM {cfg.source.table(cfg.flights.table)} "
                "WHERE day = {day_epoch} "
                f"AND (estdepartureairport = '{cfg.region.airport}' "
                f"OR estarrivalairport = '{cfg.region.airport}')"
            ),
        },
        "columns": list(STATE_VECTOR_COLUMNS),
        "flights_columns": list(FLIGHT_COLUMNS),
        "serials": {
            "included": False,
            "decision": "excluded from v1 after the 2026-07-15 A/B test",
        },
        "partitioning": {
            "state_vectors": (
                "bronze/opensky/state_vectors/<dataset>/<version>/dt=YYYY-MM-DD/hour-HH.parquet"
            ),
            "flights": ("bronze/opensky/flights/<airport>/<version>/dt=YYYY-MM-DD/flights.parquet"),
        },
        "flights_dataset": {
            "id": cfg.flights.dataset_id,
            "version": cfg.flights.version,
            "day_end": cfg.flights.day_end.isoformat(),
        },
        "known_gaps": [{"start": iso(gap.start), "end": iso(gap.end)} for gap in gaps],
        "processing_epochs": [
            {
                "id": epoch.id,
                "start": None if epoch.start is None else iso(epoch.start),
                "note": epoch.note,
            }
            for epoch in epochs
        ],
        "written_at": iso(now or utc_now()),
        "tool_version": __version__,
    }


def _batch_index() -> tuple[dict[int, str], dict[int, str]]:
    batch_of_hour: dict[int, str] = {}
    batch_of_day: dict[int, str] = {}
    for batch in load_batches().values():
        for hour in batch.hours():
            batch_of_hour[int(hour.timestamp())] = batch.id
        for day in batch.flight_days():
            batch_of_day[int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp())] = (
                batch.id
            )
    return batch_of_hour, batch_of_day


def _index_rows(root: Path, table: str, key: str) -> list[dict[str, Any]]:
    db = sqlite3.connect(root / "metadata" / "state.db")
    db.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY {key}")]
    finally:
        db.close()


def _hour_row(row: dict[str, Any], batch_of_hour: dict[int, str], cfg: Config) -> dict[str, Any]:
    stamp = int(row["hour"])
    path = row["relative_path"]
    return {
        "hour_epoch": stamp,
        "hour": datetime.fromtimestamp(stamp, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dataset_id": cfg.region.id,
        "dataset_version": cfg.region.version,
        "batch_id": batch_of_hour.get(stamp),
        "status": row["status"],
        "rows": row["rows"],
        "bytes": row["bytes"],
        "sha256": row["sha256"],
        "path": str(cfg.paths.data_root / path) if path else None,
        "attempts": row["attempts"],
        "run_id": row["run_id"],
        "collected_at": row["updated_at"],
    }


def _flight_row(row: dict[str, Any], batch_of_day: dict[int, str], cfg: Config) -> dict[str, Any]:
    stamp = int(row["day"])
    path = row["relative_path"]
    return {
        "day_epoch": stamp,
        "day": datetime.fromtimestamp(stamp, tz=UTC).strftime("%Y-%m-%d"),
        "dataset_id": cfg.flights.dataset_id,
        "dataset_version": cfg.flights.version,
        "batch_id": batch_of_day.get(stamp),
        "status": row["status"],
        "rows": row["rows"],
        "bytes": row["bytes"],
        "sha256": row["sha256"],
        "path": str(cfg.paths.data_root / path) if path else None,
        "attempts": row["attempts"],
        "run_id": row["run_id"],
        "collected_at": row["updated_at"],
    }


def _batch_manifest_ids(root: Path) -> list[str]:
    directory = root / "metadata" / "manifests" / "batches"
    if not directory.exists():
        return []
    return sorted(path.stem for path in directory.glob("*.json"))


def _batch_rows(root: Path, batches: dict) -> list[dict[str, Any]]:
    rows = []
    for batch_id in _batch_manifest_ids(root):
        manifest = _read_json(root / "metadata" / "manifests" / "batches" / f"{batch_id}.json")
        if manifest is None:
            continue
        acceptance = _read_json(root / "metadata" / "acceptance" / f"{batch_id}.json")
        published = _read_json(root / "metadata" / "published" / f"{batch_id}.json")
        batch = batches.get(batch_id)
        rows.append(
            {
                "batch_id": batch_id,
                "month": manifest["month"],
                "state_from": None if batch is None else batch.state_from.isoformat(),
                "state_until": None if batch is None else batch.state_until.isoformat(),
                "expected_hours": manifest["expected_hours"],
                "complete": manifest["complete"],
                "empty": manifest["empty"],
                "source_gap": manifest["source_gap"],
                "failed": manifest["failed"],
                "rows": manifest["rows"],
                "bytes": manifest["bytes"],
                "processed_bytes": manifest["processed_bytes"],
                "flight_rows": manifest["flight_rows"],
                "flight_bytes": manifest["flight_bytes"],
                "flights_complete": manifest["flights_complete"],
                "expected_flights": manifest["expected_flights"],
                "validation_outcome": manifest["outcome"],
                "checked_at": manifest["checked_at"],
                "accepted_at": None if acceptance is None else acceptance["accepted_at"],
                "published_at": None if published is None else published["published_at"],
                "git_commit": manifest.get("git_commit"),
                "tool_version": manifest.get("tool_version"),
            }
        )
    return rows


def _read_json(path: Path) -> dict[str, Any] | None:
    import json

    if not path.exists():
        return None
    return json.loads(path.read_text())


_HOUR_FIELDS = [
    ("hour_epoch", pa.int64()),
    ("hour", pa.string()),
    ("dataset_id", pa.string()),
    ("dataset_version", pa.string()),
    ("batch_id", pa.string()),
    ("status", pa.string()),
    ("rows", pa.int64()),
    ("bytes", pa.int64()),
    ("sha256", pa.string()),
    ("path", pa.string()),
    ("attempts", pa.int64()),
    ("run_id", pa.string()),
    ("collected_at", pa.string()),
]
_FLIGHT_FIELDS = [
    ("day_epoch", pa.int64()),
    ("day", pa.string()),
    ("dataset_id", pa.string()),
    ("dataset_version", pa.string()),
    ("batch_id", pa.string()),
    ("status", pa.string()),
    ("rows", pa.int64()),
    ("bytes", pa.int64()),
    ("sha256", pa.string()),
    ("path", pa.string()),
    ("attempts", pa.int64()),
    ("run_id", pa.string()),
    ("collected_at", pa.string()),
]
_BATCH_FIELDS = [
    ("batch_id", pa.string()),
    ("month", pa.string()),
    ("state_from", pa.string()),
    ("state_until", pa.string()),
    ("expected_hours", pa.int64()),
    ("complete", pa.int64()),
    ("empty", pa.int64()),
    ("source_gap", pa.int64()),
    ("failed", pa.int64()),
    ("rows", pa.int64()),
    ("bytes", pa.int64()),
    ("processed_bytes", pa.int64()),
    ("flight_rows", pa.int64()),
    ("flight_bytes", pa.int64()),
    ("flights_complete", pa.int64()),
    ("expected_flights", pa.int64()),
    ("validation_outcome", pa.string()),
    ("checked_at", pa.string()),
    ("accepted_at", pa.string()),
    ("published_at", pa.string()),
    ("git_commit", pa.string()),
    ("tool_version", pa.string()),
]
HOUR_SCHEMA = pa.schema(_HOUR_FIELDS)
FLIGHT_SCHEMA = pa.schema(_FLIGHT_FIELDS)
BATCH_SCHEMA = pa.schema(_BATCH_FIELDS)


def _write_table(path: Path, rows: list[dict[str, Any]], schema: pa.Schema) -> None:
    columns = {
        field.name: pa.array([row.get(field.name) for row in rows], type=field.type)
        for field in schema
    }
    pq.write_table(pa.table(columns, schema=schema), path)


# ---------------------------------------------------------------------------
# DuckDB catalog


def build_catalog(cfg: Config, *, now: datetime | None = None) -> dict[str, Any]:
    """Create `metadata/datasets/catalog.duckdb` with the lakehouse views.

    `state_vectors` and `flights` read the file lists from the exported
    manifests, so only committed and accepted hours are ever visible.
    """
    import duckdb

    root = cfg.paths.data_root
    out = root / DATASETS_DIR
    hour_table = out / HOUR_MANIFEST_PARQUET
    flight_table = out / FLIGHT_MANIFEST_PARQUET
    batch_table = out / BATCH_MANIFEST_PARQUET
    missing = [str(path) for path in (hour_table, flight_table, batch_table) if not path.exists()]
    if missing:
        raise ConfigError(f"run export-manifests first; missing {', '.join(missing)}")

    hour_paths = _complete_paths(hour_table)
    flight_paths = _complete_paths(flight_table)
    db_path = out / CATALOG_NAME
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    try:
        con.execute("SET preserve_insertion_order=false")
        con.execute(f"CREATE VIEW hour_manifest AS SELECT * FROM read_parquet('{hour_table}')")
        con.execute(f"CREATE VIEW flight_manifest AS SELECT * FROM read_parquet('{flight_table}')")
        con.execute(f"CREATE VIEW batch_manifest AS SELECT * FROM read_parquet('{batch_table}')")
        gaps = load_gaps()
        values = ", ".join(f"('{iso(gap.start)}', '{iso(gap.end)}')" for gap in gaps)
        con.execute(
            "CREATE VIEW known_gaps AS SELECT * FROM (VALUES "
            + (values or "(NULL, NULL)")
            + ') AS t("start", "end")'
        )
        epochs = load_epochs()
        epoch_values = ", ".join(
            f"('{epoch.id}', {repr('' if epoch.start is None else iso(epoch.start))}, "
            f"{repr(epoch.note)})"
            for epoch in epochs
        )
        con.execute(
            "CREATE VIEW processing_epochs AS SELECT * FROM (VALUES "
            f'{epoch_values}) AS t(id, "start", note)'
        )
        if hour_paths:
            listing = "[" + ", ".join(f"'{path}'" for path in hour_paths) + "]"
            con.execute(f"CREATE VIEW state_vectors AS SELECT * FROM read_parquet({listing})")
        if flight_paths:
            listing = "[" + ", ".join(f"'{path}'" for path in flight_paths) + "]"
            con.execute(f"CREATE VIEW flights AS SELECT * FROM read_parquet({listing})")
    finally:
        con.close()
    moment = now or utc_now()
    record = {
        "catalog": str(db_path),
        "flight_files": len(flight_paths),
        "hour_files": len(hour_paths),
        "known_gaps": len(gaps),
        "run_id": new_run_id(moment),
        "tool_version": __version__,
        "views": [
            "state_vectors",
            "flights",
            "hour_manifest",
            "flight_manifest",
            "batch_manifest",
            "known_gaps",
            "processing_epochs",
        ],
        "written_at": iso(moment),
    }
    write_json_atomic(out / "catalog.json", record)
    append_event(
        root,
        {
            "at": iso(moment),
            "kind": "catalog_built",
            "hour_files": len(hour_paths),
            "flight_files": len(flight_paths),
        },
    )
    return record


def _complete_paths(table: Path) -> list[str]:
    table_reader = pq.read_table(table, columns=["path", "status"])
    statuses = table_reader.column("status").to_pylist()
    paths = table_reader.column("path").to_pylist()
    return sorted(
        path for path, status in zip(paths, statuses, strict=False) if path and status == "complete"
    )


# ---------------------------------------------------------------------------
# Dataset summary


def dataset_summary(cfg: Config, *, now: datetime | None = None) -> dict[str, Any]:
    """Aggregate the whole dataset. The distinct aircraft counts need DuckDB."""
    import duckdb

    root = cfg.paths.data_root
    out = root / DATASETS_DIR
    hour_table = out / HOUR_MANIFEST_PARQUET
    flight_table = out / FLIGHT_MANIFEST_PARQUET
    missing = [str(path) for path in (hour_table, flight_table) if not path.exists()]
    if missing:
        raise ConfigError(f"run export-manifests first; missing {', '.join(missing)}")

    hour_rows = _index_rows(root, "hours", "hour")
    flight_rows = _index_rows(root, "flight_days", "day")
    batches = load_batches()
    per_month = _per_month(root, batches)
    epochs = load_epochs()

    hour_rows_by_epoch: dict[str, int] = {}
    boundary_hours = 0
    for row in hour_rows:
        if row["status"] not in {"complete", "empty", "source_gap"}:
            continue
        start = datetime.fromtimestamp(int(row["hour"]), tz=UTC)
        label, boundary = hour_epoch_label(epochs, start)
        if row["status"] == "complete":
            hour_rows_by_epoch[label] = hour_rows_by_epoch.get(label, 0) + int(row["rows"] or 0)
        boundary_hours += int(boundary)

    con = duckdb.connect()
    try:
        con.execute("SET preserve_insertion_order=false")
        hour_paths = _complete_paths(hour_table)
        flight_paths = _complete_paths(flight_table)
        aircraft = {"state_vectors": None, "flights": None}
        if hour_paths:
            listing = "[" + ", ".join(f"'{path}'" for path in hour_paths) + "]"
            aircraft["state_vectors"] = int(
                con.execute(
                    f"SELECT count(DISTINCT icao24) FROM read_parquet({listing})"
                ).fetchone()[0]
            )
        if flight_paths:
            listing = "[" + ", ".join(f"'{path}'" for path in flight_paths) + "]"
            aircraft["flights"] = int(
                con.execute(
                    f"SELECT count(DISTINCT icao24) FROM read_parquet({listing})"
                ).fetchone()[0]
            )
    finally:
        con.close()

    gaps = load_gaps()
    moment = now or utc_now()
    record = {
        "dataset_id": cfg.region.id,
        "dataset_version": cfg.region.version,
        "flights_dataset_id": cfg.flights.dataset_id,
        "flights_dataset_version": cfg.flights.version,
        "period": {
            "start": cfg.period.start.isoformat(),
            "end": cfg.period.end.isoformat(),
        },
        "state_vectors": {
            "expected": len(hour_rows),
            **_status_counts(hour_rows),
            "rows": sum(int(row["rows"] or 0) for row in hour_rows if row["status"] == "complete"),
            "bytes": sum(
                int(row["bytes"] or 0) for row in hour_rows if row["status"] == "complete"
            ),
            "unique_aircraft": aircraft["state_vectors"],
            "rows_by_processing_epoch": hour_rows_by_epoch,
            "epoch_boundary_hours": boundary_hours,
        },
        "flights": {
            "expected": len(flight_rows),
            **_status_counts(flight_rows),
            "rows": sum(
                int(row["rows"] or 0) for row in flight_rows if row["status"] == "complete"
            ),
            "bytes": sum(
                int(row["bytes"] or 0) for row in flight_rows if row["status"] == "complete"
            ),
            "unique_aircraft": aircraft["flights"],
        },
        "per_month": per_month,
        "known_gaps": {"count": len(gaps), "hours_covered": _gap_hours(gaps)},
        "generated_at": iso(moment),
        "run_id": new_run_id(moment),
        "git_commit": git_commit(),
        "tool_version": __version__,
    }
    write_json_atomic(out / SUMMARY_NAME, record)
    append_event(root, {"at": iso(moment), "kind": "dataset_summarised"})
    return record


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"complete": 0, "empty": 0, "source_gap": 0, "other": 0}
    for row in rows:
        status = row["status"]
        counts[status] = counts.get(status, 0) + 1 if status in counts else counts["other"] + 1
    return counts


def _per_month(root: Path, batches: dict) -> list[dict[str, Any]]:
    rows = []
    for batch_id in _batch_manifest_ids(root):
        manifest = _read_json(root / "metadata" / "manifests" / "batches" / f"{batch_id}.json")
        if manifest is None:
            continue
        rows.append(
            {
                "batch_id": batch_id,
                "month": manifest["month"],
                "hours_expected": manifest["expected_hours"],
                "hours_complete": manifest["complete"],
                "hours_empty": manifest["empty"],
                "hours_source_gap": manifest["source_gap"],
                "rows": manifest["rows"],
                "bytes": manifest["bytes"],
                "flight_days_complete": manifest["flights_complete"],
                "flight_rows": manifest["flight_rows"],
            }
        )
    return rows


def _gap_hours(gaps) -> int:
    from datetime import timedelta

    total = timedelta()
    for gap in gaps:
        total += gap.end - gap.start
    return int(total.total_seconds() // 3600)
