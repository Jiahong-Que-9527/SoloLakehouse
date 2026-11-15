"""Compare the legacy 10 km box with fin hour receipts.

Fin queried `lat BETWEEN 49.98 AND 50.07 AND lon BETWEEN 8.48 AND 8.62`.
The new files cover the larger region, so this counts that inner box in each
committed hour and compares rows, aircraft, event-time bounds and ground rows.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pyarrow.compute as pc
import pyarrow.parquet as pq

from . import __version__
from .config import Config, ConfigError
from .fetch import git_commit, new_run_id
from .manifest import COMMITTED, hour_manifest_rel, hour_parquet_rel, read_manifest
from .run import iter_hours
from .util import epoch, iso, utc_now, write_json_atomic

# Inclusive bounds, matching the fin state-vector query.
SMALL_BOX = {"south": 49.98, "north": 50.07, "west": 8.48, "east": 8.62}
COMPARED = ("rows", "aircraft", "min_time", "max_time", "ground_rows")


def cross_check_hours(
    cfg: Config,
    start: datetime,
    until: datetime,
    receipts: Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Check every hour in the range against one `{epoch}.receipt.json` each."""
    if until <= start:
        raise ConfigError("until must be after from")
    last = until - timedelta(hours=1)
    if start.date() < cfg.period.start or last.date() >= cfg.period.end:
        raise ConfigError("range is outside the dataset period")
    if not receipts.is_dir():
        raise ConfigError(f"receipt directory not found: {receipts}")
    moment = now or utc_now()
    run_id = new_run_id(moment)
    hours = [_check_hour(cfg, hour, receipts) for hour in iter_hours(start, until)]
    matched = sum(1 for item in hours if item["match"])
    record = {
        "box": SMALL_BOX,
        "checked": len(hours),
        "dataset_id": cfg.region.id,
        "dataset_version": cfg.region.version,
        "from": iso(start),
        "git_commit": git_commit(),
        "hours": hours,
        "matched": matched,
        "mismatched": len(hours) - matched,
        "outcome": "matched" if matched == len(hours) else "mismatched",
        "receipts": str(receipts),
        "run_at": iso(moment),
        "run_id": run_id,
        "tool_version": __version__,
        "until": iso(until),
    }
    path = cfg.paths.data_root / "reports" / "cross-check" / f"{run_id}.json"
    write_json_atomic(path, record)
    record["path"] = str(path)
    return record


def inner_box_aggregates(path: Path) -> dict[str, Any]:
    """Count the legacy box inside one regional hour file."""
    table = pq.read_table(path, columns=["time", "icao24", "lat", "lon", "onground"])
    if table.num_rows == 0:
        return _empty()
    lat = table.column("lat")
    lon = table.column("lon")
    inside = pc.and_(
        pc.and_(pc.greater_equal(lat, SMALL_BOX["south"]), pc.less_equal(lat, SMALL_BOX["north"])),
        pc.and_(pc.greater_equal(lon, SMALL_BOX["west"]), pc.less_equal(lon, SMALL_BOX["east"])),
    )
    chosen = table.filter(inside)
    if chosen.num_rows == 0:
        return _empty()
    times = chosen.column("time")
    ground = pc.sum(pc.if_else(pc.fill_null(chosen.column("onground"), False), 1, 0)).as_py()
    return {
        "rows": chosen.num_rows,
        "aircraft": int(pc.count_distinct(chosen.column("icao24")).as_py()),
        "min_time": int(pc.min(times).as_py()),
        "max_time": int(pc.max(times).as_py()),
        "ground_rows": int(ground or 0),
    }


def _check_hour(cfg: Config, hour: datetime, receipts: Path) -> dict[str, Any]:
    root = cfg.paths.data_root
    manifest = read_manifest(root / hour_manifest_rel(hour))
    base = {"hour": iso(hour), "match": False, "mismatches": []}
    if manifest is None or manifest.get("status") not in COMMITTED:
        return {**base, "mismatches": ["missing_manifest"]}
    path = root / hour_parquet_rel(cfg.region.id, cfg.region.version, hour)
    if manifest["status"] != "complete" or not path.exists():
        local = _empty()
    else:
        local = inner_box_aggregates(path)
    receipt_path = receipts / f"{epoch(hour)}.receipt.json"
    if not receipt_path.exists():
        return {**base, "file": local, "mismatches": ["missing_receipt"]}
    receipt = json.loads(receipt_path.read_text())
    expected = {name: receipt.get(name) for name in COMPARED}
    mismatches = [name for name in COMPARED if not _same(local[name], expected[name])]
    return {
        "hour": iso(hour),
        "match": not mismatches,
        "mismatches": mismatches,
        "file": local,
        "receipt": expected,
    }


def _empty() -> dict[str, Any]:
    return {"rows": 0, "aircraft": 0, "min_time": None, "max_time": None, "ground_rows": 0}


def _same(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is None and right is None
    return int(left) == int(right) 
