"""Read-only discovery: tables, schemas and partition availability.

Run before any collection. The output is a JSON record kept under the data
root. It settles the Arrow types, shows whether the whole period is available
and gives a first volume signal from a few sampled hours.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any

from . import __version__
from .config import Config
from .errors import AuthRequired, SourceError
from .reference import hour_epoch_label, hour_gap_status, load_epochs, load_gaps
from .trino_client import fetch_all
from .util import day_epoch, epoch, iso, utc_now, write_json_atomic

# Columns documented for flights_data4 (OpenSky Trino documentation).
FLIGHTS_DOCUMENTED = (
    "icao24",
    "firstseen",
    "estdepartureairport",
    "lastseen",
    "estarrivalairport",
    "callsign",
    "track",
    "estdepartureairporthorizdistance",
    "estdepartureairportvertdistance",
    "estarrivalairporthorizdistance",
    "estarrivalairportvertdistance",
    "departureairportcandidatescount",
    "arrivalairportcandidatescount",
    "otherdepartureairportcandidates",
    "otherarrivalairportcandidates",
    "day",
)


def _safe(action: Callable[[], dict[str, Any]], issues: list[str], label: str) -> dict[str, Any]:
    """Run one probe. Record a source error and continue. Auth errors stop the run."""
    try:
        return action()
    except AuthRequired:
        raise
    except SourceError as exc:
        issues.append(f"{label}: {exc.error_class}")
        return {"error": exc.error_class}


def describe_table(
    connection: Any, cfg: Config, table: str, expected: tuple[str, ...], optional: tuple[str, ...]
) -> dict[str, Any]:
    rows, info = fetch_all(
        connection,
        f"DESCRIBE {cfg.source.table(table)}",
        timeout=cfg.source.query_timeout_seconds,
    )
    columns = [{"name": r[0], "type": r[1]} for r in rows]
    names = {c["name"] for c in columns}
    return {
        "table": table,
        "columns": columns,
        "missing_expected": sorted(set(expected) - names),
        "unexpected": sorted(names - set(expected) - set(optional)),
        "optional_present": sorted(set(optional) & names),
        "query_id": info.query_id,
    }


def probe_hour_exists(connection: Any, cfg: Config, hour: datetime) -> dict[str, Any]:
    table = cfg.source.table(cfg.state_vectors.table)
    rows, info = fetch_all(
        connection,
        f"SELECT 1 FROM {table} WHERE hour = {epoch(hour)} LIMIT 1",
        timeout=cfg.source.query_timeout_seconds,
    )
    return {
        "hour": iso(hour),
        "hour_epoch": epoch(hour),
        "has_rows": bool(rows),
        "query_id": info.query_id,
        "elapsed_seconds": round(info.elapsed_seconds, 3),
        "processed_bytes": info.processed_bytes,
    }


def probe_hour_rows(connection: Any, cfg: Config, hour: datetime) -> dict[str, Any]:
    box = cfg.region.bbox
    table = cfg.source.table(cfg.state_vectors.table)
    sql = (
        "SELECT count(*), count(DISTINCT icao24), count_if(onground), min(time), max(time) "
        f"FROM {table} WHERE hour = {epoch(hour)} "
        f"AND lat BETWEEN {box.south} AND {box.north} "
        f"AND lon BETWEEN {box.west} AND {box.east}"
    )
    rows, info = fetch_all(connection, sql, timeout=cfg.source.query_timeout_seconds)
    count, aircraft, ground, low, high = rows[0] if rows else (0, 0, 0, None, None)
    return {
        "hour": iso(hour),
        "hour_epoch": epoch(hour),
        "rows_in_box": count,
        "aircraft": aircraft,
        "ground_rows": ground,
        "min_time": low,
        "max_time": high,
        "query_id": info.query_id,
        "elapsed_seconds": round(info.elapsed_seconds, 3),
        "processed_bytes": info.processed_bytes,
    }


def probe_flights(connection: Any, cfg: Config, day: date) -> dict[str, Any]:
    table = cfg.source.table(cfg.flights.table)
    airport = cfg.region.airport
    sql = (
        f"SELECT count(*), count_if(estdepartureairport = '{airport}'), "
        f"count_if(estarrivalairport = '{airport}') FROM {table} "
        f"WHERE day = {day_epoch(day)} "
        f"AND (estdepartureairport = '{airport}' OR estarrivalairport = '{airport}')"
    )
    rows, info = fetch_all(connection, sql, timeout=cfg.source.query_timeout_seconds)
    total, departures, arrivals = rows[0] if rows else (0, 0, 0)
    return {
        "day": day.isoformat(),
        "day_epoch": day_epoch(day),
        "flights": total,
        "departures": departures,
        "arrivals": arrivals,
        "query_id": info.query_id,
        "elapsed_seconds": round(info.elapsed_seconds, 3),
        "processed_bytes": info.processed_bytes,
    }


def discover(
    connection: Any,
    cfg: Config,
    *,
    progress: Callable[[str], None] = print,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Run all discovery probes and return the record. Raises AuthRequired if the
    session is missing or has expired."""
    gaps = load_gaps()
    epochs = load_epochs()
    issues: list[str] = []
    record: dict[str, Any] = {
        "tool_version": __version__,
        "run_at": iso(now or utc_now()),
        "dataset": {
            "id": cfg.region.id,
            "version": cfg.region.version,
            "bbox": vars(cfg.region.bbox),
            "period_start": cfg.period.start.isoformat(),
            "period_end_exclusive": cfg.period.end.isoformat(),
            "expected_hours": cfg.period.hours,
        },
    }

    progress("Listing tables")
    rows, _ = fetch_all(
        connection,
        f"SHOW TABLES FROM {cfg.source.catalog}.{cfg.source.schema}",
        timeout=cfg.source.query_timeout_seconds,
    )
    tables = sorted(r[0] for r in rows)
    record["tables"] = tables
    for needed in (cfg.state_vectors.table, cfg.flights.table):
        if needed not in tables:
            issues.append(f"TABLE_NOT_VISIBLE: {needed}")

    progress("Describing tables")
    record["schemas"] = {}
    if cfg.state_vectors.table in tables:
        record["schemas"][cfg.state_vectors.table] = describe_table(
            connection,
            cfg,
            cfg.state_vectors.table,
            cfg.state_vectors.columns,
            cfg.state_vectors.optional_columns,
        )
    if cfg.flights.table in tables:
        record["schemas"][cfg.flights.table] = describe_table(
            connection, cfg, cfg.flights.table, FLIGHTS_DOCUMENTED, ()
        )
    for name, schema in record["schemas"].items():
        if schema["missing_expected"]:
            issues.append(f"SCHEMA_DRIFT: {name} lacks {schema['missing_expected']}")

    progress("Probing hour partitions")
    record["hour_probes"] = []
    for hour in cfg.discovery.hour_probes:
        result = _safe(lambda h=hour: probe_hour_exists(connection, cfg, h), issues, iso(hour))
        gap = hour_gap_status(gaps, hour)
        result.update({"hour": iso(hour), "known_gap": gap})
        label, boundary = hour_epoch_label(epochs, hour)
        result.update({"processing_epoch": label, "epoch_boundary": boundary})
        if result.get("has_rows") is False and gap == "none":
            issues.append(f"HOUR_PARTITION_EMPTY: {iso(hour)}")
        record["hour_probes"].append(result)

    progress("Counting rows inside the box for sample hours")
    record["rowcount_probes"] = [
        _safe(lambda h=hour: probe_hour_rows(connection, cfg, h), issues, iso(hour))
        for hour in cfg.discovery.rowcount_probe_hours
    ]

    progress("Counting flights for sample days")
    record["flight_probes"] = [
        _safe(lambda d=day: probe_flights(connection, cfg, d), issues, day.isoformat())
        for day in cfg.discovery.flight_probe_days
    ]

    counted = [p for p in record["rowcount_probes"] if "rows_in_box" in p]
    if counted:
        record["row_estimates"] = {
            "rows_in_box_per_sampled_hour": [p["rows_in_box"] for p in counted],
            "mean_rows_per_hour": round(sum(p["rows_in_box"] for p in counted) / len(counted)),
            "mean_processed_bytes": round(
                sum(p["processed_bytes"] or 0 for p in counted) / len(counted)
            ),
        }
    record["issues"] = issues
    record["window_available"] = not any(
        i.startswith(("TABLE_NOT_VISIBLE", "HOUR_PARTITION_EMPTY", "SCHEMA_DRIFT")) for i in issues
    )
    return record


def record_path(cfg: Config, run_at: str) -> Path:
    stamp = run_at.replace("-", "").replace(":", "")
    return cfg.paths.data_root / "metadata" / "schemas" / f"discovery-{stamp}.json"


def save_record(cfg: Config, record: dict[str, Any]) -> Path:
    path = record_path(cfg, record["run_at"])
    write_json_atomic(path, record)
    return path


def summarise(record: dict[str, Any]) -> list[str]:
    """Short human-readable summary lines."""
    lines = [f"Tables visible: {len(record['tables'])}"]
    for name, schema in record["schemas"].items():
        lines.append(
            f"{name}: {len(schema['columns'])} columns, "
            f"missing {schema['missing_expected'] or 'none'}, "
            f"unexpected {schema['unexpected'] or 'none'}, "
            f"optional present {schema['optional_present'] or 'none'}"
        )
    present = sum(1 for p in record["hour_probes"] if p.get("has_rows"))
    lines.append(f"Hour partitions with rows: {present} of {len(record['hour_probes'])} probed")
    estimates = record.get("row_estimates")
    if estimates:
        lines.append(
            f"Rows in box per sampled hour (mean): {estimates['mean_rows_per_hour']:,}; "
            f"scanned per query (mean): {estimates['mean_processed_bytes'] / 1e9:.2f} GB"
        )
    flights = [p["flights"] for p in record["flight_probes"] if "flights" in p]
    if flights:
        lines.append(f"Flights per sampled day (EDDF): {flights}")
    lines.append("Issues: " + ("; ".join(record["issues"]) if record["issues"] else "none"))
    lines.append(f"Whole window available: {'yes' if record['window_available'] else 'NO'}")
    return lines
