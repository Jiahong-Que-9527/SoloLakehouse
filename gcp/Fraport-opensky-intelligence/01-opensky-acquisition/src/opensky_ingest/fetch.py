"""Collect one state-vector hour and commit it.

The hour manifest is the commit marker. SQLite and the ledger are updated
after that rename. A repeat run skips a committed hour. Staging files are
disposable. A final file without a manifest is an orphan and is redone.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from . import __version__
from .config import Config, ConfigError
from .discover import probe_hour_exists
from .errors import IngestError, SourceError
from .manifest import (
    COMMITTED,
    hour_manifest_rel,
    hour_parquet_rel,
    read_manifest,
    sha256_file,
    write_manifest,
)
from .parquet_writer import table_from_rows, write_hour_table
from .query import sql_sha256, state_vector_sql
from .reference import hour_epoch_label, hour_gap_status, load_epochs, load_gaps
from .schema import SCHEMA_VERSION, STATE_VECTOR_COLUMNS, TRINO_TYPES, state_vector_schema
from .state import append_event, connect, record_hour, record_run
from .trino_client import fetch_all, run_query
from .util import epoch, fsync_dir, iso, utc_now
from .validate import validate_hour_table

ROW_CAP = 1_000_000
SIZE_CAP = 400 * 1024 * 1024
SCAN_CAP = 20 * 1024**3


class InjectedCrash(RuntimeError):
    """Raised only by tests, after a named commit step has finished."""

    def __init__(self, step: str) -> None:
        super().__init__(step)
        self.step = step


def new_run_id(now: datetime) -> str:
    return now.strftime("%Y%m%dT%H%M%SZ") + "-" + os.urandom(2).hex()


def git_commit() -> str:
    root = _repo_root()
    if root is None:
        return "unknown"
    try:
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    dirty = subprocess.call(
        ["git", "diff", "--quiet"],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return head + ("-dirty" if dirty else "")


def collect_hour(
    connection: Any,
    cfg: Config,
    hour: datetime,
    *,
    run_id: str | None = None,
    crash_after: str | None = None,
    row_cap: int = ROW_CAP,
    size_cap: int = SIZE_CAP,
    pause_seconds: float = 0.0,
    progress: Callable[[str], None] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Collect one hour. Returns the manifest plus an `outcome` key."""
    hour = hour.astimezone(UTC)
    if hour.date() < cfg.period.start or hour.date() >= cfg.period.end:
        raise ConfigError("hour is outside the dataset period")
    moment = now or utc_now()
    run_id = run_id or new_run_id(moment)
    root = cfg.paths.data_root
    rel_parquet = hour_parquet_rel(cfg.region.id, cfg.region.version, hour)
    final = root / rel_parquet
    manifest_path = root / hour_manifest_rel(hour)
    existing = read_manifest(manifest_path)

    if existing and existing.get("status") in COMMITTED:
        problem = _commit_problem(existing, final)
        if problem is None:
            return {**existing, "outcome": "skipped"}
        return _mark_corrupt(cfg, existing, final, manifest_path, problem, run_id, moment)

    if existing and existing.get("status") == "failed" and final.exists():
        _quarantine(final, root, run_id)
    elif final.exists():
        _quarantine(final, root, run_id)

    assert_source_schema(connection, cfg)
    _pause(pause_seconds)
    sql = state_vector_sql(cfg, hour)
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
        return _fail(cfg, hour, run_id, exc.error_class, moment)
    if list(info.columns) != list(STATE_VECTOR_COLUMNS):
        raise IngestError("SCHEMA_DRIFT: query columns differ from the contract")
    if info.processed_bytes is not None and info.processed_bytes > SCAN_CAP:
        return _fail(cfg, hour, run_id, "SCAN_LIMIT_EXCEEDED", moment, query_id=info.query_id)
    _checkpoint("queried", crash_after)

    gaps = load_gaps()
    epochs = load_epochs()
    gap = hour_gap_status(gaps, hour)
    label, boundary = hour_epoch_label(epochs, hour)
    common = _common(
        cfg,
        hour,
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
        probe = probe_hour_exists(connection, cfg, hour)
        _checkpoint("probed", crash_after)
        if probe["has_rows"]:
            status = "empty"
        elif gap == "inside":
            status = "source_gap"
        else:
            return _fail(cfg, hour, run_id, "SOURCE_MISSING", moment, query_id=info.query_id)
        manifest = _empty_manifest(common, status, gap, boundary)
        return _commit(cfg, manifest, manifest_path, crash_after)

    staged = root / "staging" / run_id / f"hour-{hour:%H}.parquet"
    schema = state_vector_schema()
    write_hour_table(table_from_rows(rows, schema), staged)
    _checkpoint("staged", crash_after)
    read_back = pq.read_table(staged)
    if read_back.num_rows != len(rows):
        _quarantine(staged, root, run_id)
        return _fail(cfg, hour, run_id, "VALIDATION", moment, query_id=info.query_id)
    try:
        stats = validate_hour_table(
            read_back, schema=schema, hour_epoch=epoch(hour), bbox=cfg.region.bbox
        )
    except SourceError:
        _quarantine(staged, root, run_id)
        return _fail(cfg, hour, run_id, "VALIDATION", moment, query_id=info.query_id)
    size = staged.stat().st_size
    if size > size_cap:
        _quarantine(staged, root, run_id)
        return _fail(cfg, hour, run_id, "SIZE_CAP", moment, query_id=info.query_id)
    _checkpoint("validated", crash_after)

    try:
        _publish(staged, final)
    except IngestError:
        _quarantine(staged, root, run_id)
        return _fail(cfg, hour, run_id, "REFUSING_OVERWRITE", moment, query_id=info.query_id)
    _checkpoint("published", crash_after)

    flags = _flags(gap, boundary, "complete")
    manifest = {
        **common,
        "status": "complete",
        "path": rel_parquet,
        "rows": stats.rows,
        "bytes": size,
        "sha256": sha256_file(final),
        "compression": "zstd",
        "aircraft": stats.aircraft,
        "ground_rows": stats.ground_rows,
        "stale_or_unknown_rows": stats.stale_or_unknown_rows,
        "duplicate_key_rows": stats.duplicate_key_rows,
        "nulls": stats.nulls,
        "min_time": stats.min_time,
        "max_time": stats.max_time,
        "flags": flags,
    }
    return _commit(cfg, manifest, manifest_path, crash_after)


def assert_source_schema(connection: Any, cfg: Config) -> None:
    """Stop the run if a collected column is missing or its Trino type changed."""
    rows, _ = fetch_all(
        connection,
        f"DESCRIBE {cfg.source.table(cfg.state_vectors.table)}",
        timeout=cfg.source.query_timeout_seconds,
    )
    found = {row[0]: row[1] for row in rows}
    drifted = [name for name, expected in TRINO_TYPES.items() if found.get(name) != expected]
    if drifted:
        detail = ", ".join(f"{name}={found.get(name)!r}" for name in drifted)
        raise IngestError(f"SCHEMA_DRIFT: {detail}")


def _commit(cfg: Config, manifest: dict, path: Path, crash_after: str | None) -> dict:
    write_manifest(path, manifest)
    _checkpoint("manifest", crash_after)
    _index(cfg, manifest, error_class=None, kind="hour_committed")
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
    """Keep the evidence, but do not leave a committed manifest pointing at it."""
    if final.exists():
        _quarantine(final, cfg.paths.data_root, run_id)
    updated = {**existing, "status": "failed", "error_class": problem, "failed_at": iso(moment)}
    write_manifest(manifest_path, updated)
    _index(cfg, updated, error_class=problem, kind="hour_failed")
    return {**updated, "outcome": "failed"}


def _fail(
    cfg: Config,
    hour: datetime,
    run_id: str,
    error_class: str,
    moment: datetime,
    *,
    query_id: str | None = None,
) -> dict:
    payload = {
        "hour": epoch(hour),
        "status": "failed",
        "rows": None,
        "bytes": None,
        "sha256": None,
        "path": None,
        "run_id": run_id,
        "collected_at": iso(moment),
        "query_id": query_id,
    }
    _index(cfg, payload, error_class=error_class, kind="hour_failed")
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
        "ground_rows": 0,
        "stale_or_unknown_rows": 0,
        "duplicate_key_rows": 0,
        "nulls": {},
        "min_time": None,
        "max_time": None,
        "flags": _flags(gap, boundary, status),
    }


def _common(
    cfg: Config,
    hour: datetime,
    run_id: str,
    moment: datetime,
    sql: str,
    query_id: str | None,
    processed_bytes: int | None,
    elapsed_seconds: float,
    label: str,
) -> dict:
    return {
        "dataset_id": cfg.region.id,
        "dataset_version": cfg.region.version,
        "hour": epoch(hour),
        "window_start": iso(hour),
        "query_id": query_id,
        "processed_bytes": processed_bytes,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "sql_sha256": sql_sha256(sql),
        "schema_version": SCHEMA_VERSION,
        "include_serials": False,
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
        record_hour(db, manifest, error_class=error_class)
    finally:
        db.close()
    append_event(
        root,
        {
            "at": manifest["collected_at"],
            "error_class": error_class,
            "hour": manifest["hour"],
            "kind": kind,
            "run_id": manifest["run_id"],
            "status": manifest["status"],
        },
    )


def _publish(staged: Path, final: Path) -> None:
    if final.exists():
        raise IngestError("REFUSING_OVERWRITE")
    final.parent.mkdir(parents=True, exist_ok=True)
    os.link(staged, final)
    _fsync_file(final)
    fsync_dir(final.parent)
    staged.unlink()
    fsync_dir(staged.parent)


def _quarantine(path: Path, root: Path, run_id: str) -> Path:
    dest_dir = root / "quarantine" / run_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / path.name
    if dest.exists():
        dest = dest_dir / f"{path.stem}-{os.urandom(2).hex()}{path.suffix}"
    os.replace(path, dest)
    return dest


def _checkpoint(step: str, crash_after: str | None) -> None:
    if crash_after == step:
        raise InjectedCrash(step)


def _pause(seconds: float) -> None:
    if seconds:
        import time

        time.sleep(seconds)


def _fsync_file(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _repo_root() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists():
            return parent
    return None
