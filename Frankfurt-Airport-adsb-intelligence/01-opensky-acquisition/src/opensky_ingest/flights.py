"""Collect one flights_data4 day and commit it.

The day manifest is the commit marker. A flight day is indexed separately from
state-vector hours: the day epoch is the same integer as hour 00 of that day.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from . import __version__
from .config import Config, ConfigError
from .errors import IngestError, SourceError
from .fetch import (
    ROW_CAP,
    SCAN_CAP,
    SIZE_CAP,
    _checkpoint,
    _pause,
    _publish,
    _quarantine,
    git_commit,
    new_run_id,
)
from .manifest import (
    COMMITTED,
    flight_manifest_rel,
    flight_parquet_rel,
    read_manifest,
    sha256_file,
    write_manifest,
)
from .parquet_writer import table_from_rows, write_flight_table
from .query import flight_sql, sql_sha256
from .reference import day_epoch_label, day_gap_status, load_epochs, load_gaps
from .schema import (
    CANDIDATE_FIELDS,
    FLIGHT_COLUMNS,
    FLIGHT_TRINO_TYPES,
    SCHEMA_VERSION,
    TRACK_FIELDS,
    flight_schema,
)
from .state import append_event, connect, record_flight_day, record_run
from .trino_client import fetch_all, run_query
from .util import day_epoch, fsync_dir, iso, utc_now
from .validate import validate_flight_table


def iter_days(start: date, until: date) -> Iterator[date]:
    """Days from `start` inclusive to `until` exclusive."""
    if until <= start:
        raise ConfigError("until must be after from")
    current = start
    while current < until:
        yield current
        current += timedelta(days=1)


def collect_flight_range(
    connection: Any,
    cfg: Config,
    start: date,
    until: date,
    *,
    max_duration: timedelta = timedelta(hours=3),
    pause_seconds: float = 0.5,
    progress: Callable[[str], None] | None = None,
    on_day: Callable[[dict[str, Any]], None] | None = None,
    clock: Callable[[], float] = time.monotonic,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Collect each pending flight day. Stops on the first day that does not commit."""
    last = until - timedelta(days=1)
    if start < cfg.period.start or last >= cfg.flights.day_end:
        raise ConfigError("range is outside the flights period")
    moment = now or utc_now()
    run_id = new_run_id(moment)
    started = clock()
    committed = 0
    skipped = 0
    limit = max_duration.total_seconds()

    for day in iter_days(start, until):
        if clock() - started >= limit:
            return _summary("stopped", "max_duration", committed, skipped, next_day=day)
        result = collect_flight_day(
            connection,
            cfg,
            day,
            run_id=run_id,
            pause_seconds=pause_seconds,
            progress=progress,
        )
        if on_day:
            shown = result
            if not shown.get("window_start"):
                shown = {**result, "window_start": day.isoformat()}
            on_day(shown)
        outcome = result["outcome"]
        if outcome == "committed":
            committed += 1
        elif outcome == "skipped":
            skipped += 1
        else:
            return _summary(
                "stopped",
                "day_failed",
                committed,
                skipped,
                next_day=day,
                error_class=result.get("error_class"),
            )
    return _summary("finished", None, committed, skipped)


def collect_flight_day(
    connection: Any,
    cfg: Config,
    day: date,
    *,
    run_id: str | None = None,
    crash_after: str | None = None,
    row_cap: int = ROW_CAP,
    size_cap: int = SIZE_CAP,
    pause_seconds: float = 0.0,
    progress: Callable[[str], None] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Collect one flight day. Returns the manifest plus an `outcome` key."""
    if day < cfg.period.start or day >= cfg.flights.day_end:
        raise ConfigError("day is outside the flights period")
    moment = now or utc_now()
    run_id = run_id or new_run_id(moment)
    root = cfg.paths.data_root
    rel_parquet = flight_parquet_rel(cfg.region.airport, cfg.flights.version, day)
    final = root / rel_parquet
    manifest_path = root / flight_manifest_rel(day)
    existing = read_manifest(manifest_path)

    if existing and existing.get("status") in COMMITTED:
        problem = _commit_problem(existing, final)
        if problem is None:
            return {**existing, "outcome": "skipped"}
        return _mark_corrupt(cfg, existing, final, manifest_path, problem, run_id, moment)

    if final.exists():
        _quarantine(final, root, run_id)

    _assert_flight_schema(connection, cfg)
    _pause(pause_seconds)
    sql = flight_sql(cfg, day)
    rows: list[tuple] = []

    def consume(row: tuple) -> None:
        if len(rows) >= row_cap:
            raise SourceError("ROW_CAP_EXCEEDED")
        rows.append(tuple(row))
        if progress and len(rows) % 50_000 == 0:
            progress(f"fetched {len(rows)} rows")

    try:
        info = run_query(connection, sql, consume, timeout=cfg.source.query_timeout_seconds)
    except SourceError as exc:
        return _fail(cfg, day, run_id, exc.error_class, moment)
    if list(info.columns) != list(FLIGHT_COLUMNS):
        raise IngestError("SCHEMA_DRIFT: query columns differ from the contract")
    if info.processed_bytes is not None and info.processed_bytes > SCAN_CAP:
        return _fail(cfg, day, run_id, "SCAN_LIMIT_EXCEEDED", moment, query_id=info.query_id)
    _checkpoint("queried", crash_after)

    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    gap = day_gap_status(load_gaps(), start)
    label, boundary = day_epoch_label(load_epochs(), start)
    common = _common(
        cfg,
        day,
        run_id,
        moment,
        sql,
        info.query_id,
        info.processed_bytes,
        info.elapsed_seconds,
        label,
    )

    if not rows:
        _pause(pause_seconds)
        probe = _probe_day_exists(connection, cfg, day)
        _checkpoint("probed", crash_after)
        if probe["has_rows"]:
            status = "empty"
        elif gap in {"inside", "overlap"}:
            # Flight rows live in one partition per source day. A documented gap
            # that covers only part of the day still drops that whole partition.
            status = "source_gap"
        else:
            return _fail(cfg, day, run_id, "SOURCE_MISSING", moment, query_id=info.query_id)
        manifest = _empty_manifest(common, status, gap, boundary)
        return _commit(cfg, manifest, manifest_path, crash_after)

    staged = root / "staging" / run_id / f"flights-{day.isoformat()}.parquet"
    schema = flight_schema()
    normalized = _normalize(rows)
    write_flight_table(table_from_rows(normalized, schema), staged)
    _checkpoint("staged", crash_after)
    read_back = pq.read_table(staged)
    if read_back.num_rows != len(rows):
        _quarantine(staged, root, run_id)
        return _fail(cfg, day, run_id, "VALIDATION", moment, query_id=info.query_id)
    try:
        stats = validate_flight_table(
            read_back, schema=schema, day_epoch=day_epoch(day), airport=cfg.region.airport
        )
    except SourceError:
        _quarantine(staged, root, run_id)
        return _fail(cfg, day, run_id, "VALIDATION", moment, query_id=info.query_id)
    size = staged.stat().st_size
    if size > size_cap:
        _quarantine(staged, root, run_id)
        return _fail(cfg, day, run_id, "SIZE_CAP", moment, query_id=info.query_id)
    _checkpoint("validated", crash_after)

    try:
        _publish(staged, final)
    except IngestError:
        _quarantine(staged, root, run_id)
        return _fail(cfg, day, run_id, "REFUSING_OVERWRITE", moment, query_id=info.query_id)
    _checkpoint("published", crash_after)
    fsync_dir(final.parent)

    manifest = {
        **common,
        "status": "complete",
        "path": rel_parquet,
        "rows": stats.rows,
        "bytes": size,
        "sha256": sha256_file(final),
        "compression": "zstd",
        "aircraft": stats.aircraft,
        "departures": stats.departures,
        "arrivals": stats.arrivals,
        "duplicate_key_rows": stats.duplicate_key_rows,
        "nulls": stats.nulls,
        "flags": _flags(gap, boundary, "complete"),
    }
    return _commit(cfg, manifest, manifest_path, crash_after)


def _assert_flight_schema(connection: Any, cfg: Config) -> None:
    rows, _ = fetch_all(
        connection,
        f"DESCRIBE {cfg.source.table(cfg.flights.table)}",
        timeout=cfg.source.query_timeout_seconds,
    )
    found = {row[0]: row[1] for row in rows}
    drifted = [name for name, expected in FLIGHT_TRINO_TYPES.items() if found.get(name) != expected]
    if drifted:
        detail = ", ".join(f"{name}={found.get(name)!r}" for name in drifted)
        raise IngestError(f"SCHEMA_DRIFT: {detail}")


def _probe_day_exists(connection: Any, cfg: Config, day: date) -> dict[str, Any]:
    table = cfg.source.table(cfg.flights.table)
    rows, info = fetch_all(
        connection,
        f"SELECT 1 FROM {table} WHERE day = {day_epoch(day)} LIMIT 1",
        timeout=cfg.source.query_timeout_seconds,
    )
    return {"has_rows": bool(rows), "query_id": info.query_id}


def _normalize(rows: list[tuple]) -> list[tuple]:
    """Turn Trino arrays of rows into tuples pyarrow can store as list<struct>."""
    track_at = FLIGHT_COLUMNS.index("track")
    departure_at = FLIGHT_COLUMNS.index("otherdepartureairportcandidates")
    arrival_at = FLIGHT_COLUMNS.index("otherarrivalairportcandidates")
    normalized = []
    for row in rows:
        items = list(row)
        items[track_at] = _structs(items[track_at], TRACK_FIELDS)
        items[departure_at] = _structs(items[departure_at], CANDIDATE_FIELDS)
        items[arrival_at] = _structs(items[arrival_at], CANDIDATE_FIELDS)
        normalized.append(tuple(items))
    return normalized


def _structs(value: Any, fields: tuple[str, ...]) -> list[tuple] | None:
    if value is None:
        return None
    return [_struct(item, fields) for item in value]


def _struct(item: Any, fields: tuple[str, ...]) -> tuple | None:
    if item is None:
        return None
    if isinstance(item, dict):
        return tuple(item.get(name) for name in fields)
    return tuple(item)


def _commit(cfg: Config, manifest: dict, path: Path, crash_after: str | None) -> dict:
    write_manifest(path, manifest)
    _checkpoint("manifest", crash_after)
    _index(cfg, manifest, error_class=None, kind="flight_committed")
    _checkpoint("indexed", crash_after)
    return {**manifest, "outcome": "committed"}


def _commit_problem(manifest: dict, final: Path) -> str | None:
    status = manifest.get("status")
    if status == "complete":
        if not final.exists():
            return "FILE_MISSING"
        if sha256_file(final) != manifest.get("sha256"):
            return "CHECKSUM_MISMATCH"
        return None
    if status in {"empty", "source_gap"} and final.exists():
        return "FILE_UNEXPECTED"
    return None


def _mark_corrupt(
    cfg: Config,
    existing: dict,
    final: Path,
    manifest_path: Path,
    problem: str,
    run_id: str,
    moment: datetime,
) -> dict:
    if final.exists():
        _quarantine(final, cfg.paths.data_root, run_id)
    updated = {**existing, "status": "failed", "error_class": problem, "failed_at": iso(moment)}
    write_manifest(manifest_path, updated)
    _index(cfg, updated, error_class=problem, kind="flight_failed")
    return {**updated, "outcome": "failed"}


def _fail(
    cfg: Config,
    day: date,
    run_id: str,
    error_class: str,
    moment: datetime,
    *,
    query_id: str | None = None,
) -> dict:
    payload = {
        "day": day_epoch(day),
        "window_start": iso(datetime(day.year, day.month, day.day, tzinfo=UTC)),
        "status": "failed",
        "rows": None,
        "bytes": None,
        "sha256": None,
        "path": None,
        "run_id": run_id,
        "collected_at": iso(moment),
        "query_id": query_id,
    }
    _index(cfg, payload, error_class=error_class, kind="flight_failed")
    return {**payload, "outcome": "failed", "error_class": error_class}


def _empty_manifest(common: dict, status: str, gap: str, boundary: bool) -> dict:
    return {
        **common,
        "status": status,
        "path": None,
        "rows": 0,
        "bytes": 0,
        "sha256": None,
        "compression": None,
        "aircraft": 0,
        "departures": 0,
        "arrivals": 0,
        "duplicate_key_rows": 0,
        "nulls": {},
        "flags": _flags(gap, boundary, status),
    }


def _common(
    cfg: Config,
    day: date,
    run_id: str,
    moment: datetime,
    sql: str,
    query_id: str | None,
    processed_bytes: int | None,
    elapsed_seconds: float,
    label: str,
) -> dict:
    return {
        "dataset_id": cfg.flights.dataset_id,
        "dataset_version": cfg.flights.version,
        "day": day_epoch(day),
        "window_start": iso(datetime(day.year, day.month, day.day, tzinfo=UTC)),
        "query_id": query_id,
        "processed_bytes": processed_bytes,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "sql_sha256": sql_sha256(sql),
        "schema_version": SCHEMA_VERSION,
        "processing_epoch": label,
        "batch_id": None,
        "run_id": run_id,
        "tool_version": __version__,
        "git_commit": git_commit(),
        "collected_at": iso(moment),
    }


def _flags(gap: str, boundary: bool, status: str) -> list[str]:
    flags = []
    if boundary:
        flags.append("processing_epoch_boundary")
    if gap == "overlap" or (gap == "inside" and status == "complete"):
        flags.append("known_gap_overlap")
    return flags


def _index(cfg: Config, manifest: dict, *, error_class: str | None, kind: str) -> None:
    root = cfg.paths.data_root
    db = connect(root / "metadata" / "state.db")
    try:
        record_run(
            db,
            manifest["run_id"],
            manifest["collected_at"],
            __version__,
            manifest.get("git_commit", ""),
        )
        record_flight_day(db, manifest, error_class=error_class)
    finally:
        db.close()
    append_event(
        root,
        {
            "at": manifest["collected_at"],
            "day": manifest["day"],
            "error_class": error_class,
            "kind": kind,
            "run_id": manifest["run_id"],
            "status": manifest["status"],
        },
    )


def _summary(
    outcome: str,
    reason: str | None,
    committed: int,
    skipped: int,
    *,
    next_day: date | None = None,
    error_class: str | None = None,
) -> dict[str, Any]:
    return {
        "outcome": outcome,
        "reason": reason,
        "committed": committed,
        "skipped": skipped,
        "next_day": None if next_day is None else next_day.isoformat(),
        "error_class": error_class,
    }
