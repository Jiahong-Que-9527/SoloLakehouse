"""Compare committed hours with fresh OpenSky aggregates.

The comparison is count, distinct aircraft, and the minimum and maximum event
time. It reads the Parquet file, not the manifest. A manifest that disagrees
with its file is also a mismatch. The pilot checks every hour in the range.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import pyarrow.compute as pc
import pyarrow.parquet as pq

from . import __version__
from .config import Config, ConfigError
from .discover import probe_hour_rows
from .errors import AuthRequired
from .fetch import git_commit, new_run_id
from .manifest import COMMITTED, hour_manifest_rel, hour_parquet_rel, read_manifest
from .run import iter_hours
from .util import iso, utc_now, write_json_atomic

COMPARED = ("rows", "aircraft", "min_time", "max_time")


def reconcile_hours(
    connection: Any,
    cfg: Config,
    start: datetime,
    until: datetime,
    *,
    max_duration: timedelta = timedelta(hours=3),
    pause_seconds: float = 0.5,
    on_hour: Callable[[dict[str, Any]], None] | None = None,
    clock: Callable[[], float] = time.monotonic,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Check every committed hour in the range. Writes a report under the data root."""
    last = until - timedelta(hours=1)
    if start.date() < cfg.period.start or last.date() >= cfg.period.end:
        raise ConfigError("range is outside the dataset period")
    moment = now or utc_now()
    run_id = new_run_id(moment)
    started = clock()
    hours: list[dict[str, Any]] = []
    outcome = "matched"
    reason = None
    next_hour = None
    try:
        for hour in iter_hours(start, until):
            if clock() - started >= max_duration.total_seconds():
                if outcome == "matched":
                    outcome = "stopped"
                reason = "max_duration"
                next_hour = hour
                break
            if pause_seconds and hours:
                time.sleep(pause_seconds)
            checked = _check_hour(connection, cfg, hour)
            hours.append(checked)
            if on_hour:
                on_hour(checked)
            if not checked["match"]:
                outcome = "mismatched"
    except AuthRequired:
        _write(cfg, _record(cfg, run_id, moment, start, until, hours, "stopped", "auth", None))
        raise
    if outcome == "matched" and any(not item["match"] for item in hours):
        outcome = "mismatched"
    record = _record(cfg, run_id, moment, start, until, hours, outcome, reason, next_hour)
    record["path"] = str(_write(cfg, record))
    return record


def file_aggregates(path) -> dict[str, Any]:
    """Count, distinct aircraft, and event-time bounds from one hour file."""
    table = pq.read_table(path, columns=["icao24", "time"])
    if table.num_rows == 0:
        return {"rows": 0, "aircraft": 0, "min_time": None, "max_time": None}
    times = table.column("time")
    return {
        "rows": table.num_rows,
        "aircraft": int(pc.count_distinct(table.column("icao24")).as_py()),
        "min_time": int(pc.min(times).as_py()),
        "max_time": int(pc.max(times).as_py()),
    }


def _check_hour(connection: Any, cfg: Config, hour: datetime) -> dict[str, Any]:
    root = cfg.paths.data_root
    manifest = read_manifest(root / hour_manifest_rel(hour))
    base = {"hour": iso(hour), "match": False, "mismatches": []}
    if manifest is None:
        return {**base, "mismatches": ["missing_manifest"]}
    status = manifest.get("status")
    if status not in COMMITTED:
        return {**base, "status": status, "mismatches": ["not_committed"]}
    path = root / hour_parquet_rel(cfg.region.id, cfg.region.version, hour)
    if status == "complete":
        if not path.exists():
            return {**base, "status": status, "mismatches": ["file_missing"]}
        local = file_aggregates(path)
    elif path.exists():
        return {**base, "status": status, "mismatches": ["file_unexpected"]}
    else:
        local = {"rows": 0, "aircraft": 0, "min_time": None, "max_time": None}
    source = probe_hour_rows(connection, cfg, hour)
    source_values = {
        "rows": source["rows_in_box"],
        "aircraft": source["aircraft"],
        "min_time": source["min_time"],
        "max_time": source["max_time"],
    }
    mismatches = [
        name for name in COMPARED if not _same(local[name], source_values[name])
    ]
    mismatches += [
        f"manifest.{name}" for name in COMPARED if not _same(manifest.get(name), local[name])
    ]
    return {
        "hour": iso(hour),
        "status": status,
        "match": not mismatches,
        "mismatches": mismatches,
        "file": local,
        "source": source_values,
        "query_id": source["query_id"],
        "elapsed_seconds": source["elapsed_seconds"],
    }


def _same(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is None and right is None
    return int(left) == int(right)


def _record(
    cfg: Config,
    run_id: str,
    moment: datetime,
    start: datetime,
    until: datetime,
    hours: list[dict[str, Any]],
    outcome: str,
    reason: str | None,
    next_hour: datetime | None,
) -> dict[str, Any]:
    matched = sum(1 for item in hours if item["match"])
    return {
        "checked": len(hours),
        "from": iso(start),
        "git_commit": git_commit(),
        "hours": hours,
        "matched": matched,
        "mismatched": len(hours) - matched,
        "next_hour": None if next_hour is None else iso(next_hour),
        "outcome": outcome,
        "reason": reason,
        "run_at": iso(moment),
        "run_id": run_id,
        "tool_version": __version__,
        "until": iso(until),
        "dataset_id": cfg.region.id,
        "dataset_version": cfg.region.version,
    }


def _write(cfg: Config, record: dict[str, Any]):
    path = cfg.paths.data_root / "reports" / "reconcile" / f"{record['run_id']}.json"
    write_json_atomic(path, record)
    return path
