"""Dataset sign-off checks (M5): full verify and the backup restore test.

`verify_dataset` re-hashes every committed file and compares it with its
manifest, walks Bronze for orphans, and cross-checks the SQLite index.
`restore_check` recovers one batch from the `E:` backup into a scratch
directory and compares every hash with the local manifests.
"""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import __version__
from .batch import load_batches
from .config import Config
from .errors import IngestError
from .fetch import git_commit, new_run_id
from .manifest import (
    COMMITTED,
    flight_manifest_rel,
    flight_parquet_rel,
    hour_manifest_rel,
    hour_parquet_rel,
    read_manifest,
    sha256_file,
)
from .state import append_event
from .util import iso, utc_now, write_json_atomic

PROBLEM_LIMIT = 1000  # stored per report; the outcome already carries the count


def verify_dataset(
    cfg: Config,
    *,
    progress: Callable[[str], None] | None = None,
    every: int = 2000,
    now: datetime | None = None,
    batches: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Re-hash all committed files, check manifests, orphans and the index."""
    root = cfg.paths.data_root
    moment = now or utc_now()
    started = moment
    batches = batches if batches is not None else load_batches()
    problems: list[dict[str, str]] = []
    counts = {"hours": {}, "flight_days": {}}
    totals = {"rows": 0, "bytes": 0, "flight_rows": 0, "flight_bytes": 0}
    files_hashed = 0
    bytes_hashed = 0
    expected: set[str] = set()

    for batch_id in sorted(batches):
        batch = batches[batch_id]
        for hour in batch.hours():
            expected.add(hour_parquet_rel(cfg.region.id, cfg.region.version, hour))
            outcome = _unit(
                root,
                read_manifest(root / hour_manifest_rel(hour)),
                hour_parquet_rel(cfg.region.id, cfg.region.version, hour),
                problems,
                counts["hours"],
                totals,
                "hour",
            )
            files_hashed += outcome["hashed"]
            bytes_hashed += outcome["hashed_bytes"]
            if progress and files_hashed and files_hashed % every == 0:
                progress(_progress_line(files_hashed, bytes_hashed, problems, started))
        for day in batch.flight_days():
            expected.add(flight_parquet_rel(cfg.region.airport, cfg.flights.version, day))
            outcome = _unit(
                root,
                read_manifest(root / flight_manifest_rel(day)),
                flight_parquet_rel(cfg.region.airport, cfg.flights.version, day),
                problems,
                counts["flight_days"],
                totals,
                "day",
            )
            files_hashed += outcome["hashed"]
            bytes_hashed += outcome["hashed_bytes"]
            if progress and files_hashed and files_hashed % every == 0:
                progress(_progress_line(files_hashed, bytes_hashed, problems, started))

    problems.extend(_orphans(root, expected))
    problems.extend(_index_divergence(root))

    record = {
        "batches": len(batches),
        "bytes_hashed": bytes_hashed,
        "counts": counts,
        "elapsed_seconds": round((utc_now() - started).total_seconds(), 3),
        "files_hashed": files_hashed,
        "git_commit": git_commit(),
        "outcome": "passed" if not problems else "failed",
        "problems": problems[:PROBLEM_LIMIT],
        "problems_truncated": max(0, len(problems) - PROBLEM_LIMIT),
        "problems_total": len(problems),
        "run_id": new_run_id(moment),
        "tool_version": __version__,
        "totals": totals,
        "verified_at": iso(utc_now()),
    }
    path = root / "reports" / "verify" / f"{record['run_id']}.json"
    write_json_atomic(path, record)
    append_event(
        root,
        {
            "at": record["verified_at"],
            "kind": "dataset_verified",
            "outcome": record["outcome"],
            "problems": len(problems),
        },
    )
    record["path"] = str(path)
    return record


def _unit(
    root: Path,
    manifest: dict | None,
    expected: str,
    problems: list[dict[str, str]],
    counts: dict[str, int],
    totals: dict[str, int],
    key: str,
) -> dict[str, int]:
    hashed = 0
    hashed_bytes = 0
    if manifest is None:
        problems.append({key: expected, "problem": "missing_manifest"})
        counts["missing"] = counts.get("missing", 0) + 1
        return {"hashed": 0, "hashed_bytes": 0}
    status = str(manifest.get("status"))
    counts[status] = counts.get(status, 0) + 1
    if status not in COMMITTED:
        problems.append({key: expected, "problem": "not_committed", "status": status})
        return {"hashed": 0, "hashed_bytes": 0}
    if status != "complete":
        if (root / expected).exists():
            problems.append({key: expected, "problem": "unexpected_file", "status": status})
        return {"hashed": 0, "hashed_bytes": 0}
    rows = int(manifest.get("rows") or 0)
    file_bytes = int(manifest.get("bytes") or 0)
    if key == "hour":
        totals["rows"] += rows
        totals["bytes"] += file_bytes
    else:
        totals["flight_rows"] += rows
        totals["flight_bytes"] += file_bytes
    file = root / expected
    recorded_path = manifest.get("path")
    if recorded_path != expected or not file.exists():
        problems.append({key: expected, "problem": "file_missing"})
        return {"hashed": 0, "hashed_bytes": 0}
    if file.stat().st_size != file_bytes:
        problems.append({key: expected, "problem": "size"})
        return {"hashed": 0, "hashed_bytes": 0}
    if sha256_file(file) != manifest.get("sha256"):
        problems.append({key: expected, "problem": "checksum"})
        return {"hashed": 0, "hashed_bytes": 0}
    hashed = 1
    hashed_bytes = file_bytes
    return {"hashed": hashed, "hashed_bytes": hashed_bytes}


def _orphans(root: Path, expected: set[str]) -> list[dict[str, str]]:
    found = []
    bronze = root / "bronze" / "opensky"
    if not bronze.exists():
        return found
    for path in sorted(bronze.rglob("*.parquet")):
        relative = path.relative_to(root).as_posix()
        if relative not in expected:
            found.append({"file": relative, "problem": "orphan"})
    return found


def _index_divergence(root: Path) -> list[dict[str, str]]:
    """The SQLite index must agree with the manifests, which are authoritative."""
    problems = []
    db_path = root / "metadata" / "state.db"
    if not db_path.exists():
        return problems
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    try:
        for kind, table, manifest_rel, key_name in (
            ("hour", "hours", hour_manifest_rel, "hour"),
            ("day", "flight_days", flight_manifest_rel, "day"),
        ):
            for row in db.execute(f"SELECT * FROM {table}"):
                stamp = int(row[key_name])
                moment = datetime.fromtimestamp(stamp, tz=UTC)
                if kind == "hour":
                    path = root / manifest_rel(moment)
                else:
                    path = root / manifest_rel(moment.date())
                manifest = read_manifest(path)
                if manifest is None:
                    problems.append(
                        {"index": f"{kind}:{stamp}", "problem": "index_without_manifest"}
                    )
                    continue
                for field in ("status", "sha256"):
                    if str(manifest.get(field) or "") != str(row[field] or ""):
                        problems.append(
                            {"index": f"{kind}:{stamp}", "problem": f"index_{field}_mismatch"}
                        )
    finally:
        db.close()
    return problems


def _progress_line(files: int, data_bytes: int, problems: list, started: datetime) -> str:
    elapsed = max((utc_now() - started).total_seconds(), 0.001)
    rate = data_bytes / elapsed / 1_000_000
    return (
        f"verified {files} files, {data_bytes / 1_000_000_000:.1f} GB, "
        f"{rate:.0f} MB/s, problems: {len(problems)}"
    )


def restore_check(
    cfg: Config,
    batch: Any,
    *,
    keep: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Recover one batch from the backup disk and verify every hash."""
    root = cfg.paths.data_root
    backup = cfg.paths.backup_root
    moment = now or utc_now()
    batch_id = batch.id
    published = read_manifest(root / "metadata" / "published" / f"{batch_id}.json")
    if published is None:
        raise IngestError("BATCH_NOT_PUBLISHED")

    target = root / "staging" / f"restore-{batch_id}"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    checked = 0
    mismatches: list[str] = []
    bytes_checked = 0
    for hour in batch.hours():
        relative = hour_parquet_rel(cfg.region.id, cfg.region.version, hour)
        manifest = read_manifest(root / hour_manifest_rel(hour))
        bytes_checked += _restore_one(root, backup, target, relative, manifest, mismatches)
        checked += 1
    for day in batch.flight_days():
        relative = flight_parquet_rel(cfg.region.airport, cfg.flights.version, day)
        manifest = read_manifest(root / flight_manifest_rel(day))
        bytes_checked += _restore_one(root, backup, target, relative, manifest, mismatches)
        checked += 1

    if not keep:
        shutil.rmtree(target)
    record = {
        "batch_id": batch_id,
        "bytes": bytes_checked,
        "checked": checked,
        "mismatches": mismatches[:PROBLEM_LIMIT],
        "mismatches_total": len(mismatches),
        "outcome": "passed" if not mismatches else "failed",
        "restored_to": None if not keep else str(target),
        "run_id": new_run_id(moment),
        "tool_version": __version__,
        "git_commit": git_commit(),
        "checked_at": iso(utc_now()),
    }
    path = root / "reports" / "restore" / f"{record['run_id']}.json"
    write_json_atomic(path, record)
    append_event(
        root,
        {
            "at": record["checked_at"],
            "batch_id": batch_id,
            "kind": "restore_checked",
            "outcome": record["outcome"],
        },
    )
    record["path"] = str(path)
    return record


def _restore_one(
    root: Path,
    backup: Path,
    target: Path,
    relative: str,
    manifest: dict | None,
    mismatches: list[str],
) -> int:
    """Copy one file from the backup and compare it with the manifest hash.

    Committed hours without a file (`source_gap`, `empty`) are skipped: their
    emptiness is the recorded outcome.
    """
    if manifest is None:
        mismatches.append(f"{relative}: no manifest")
        return 0
    if str(manifest.get("status")) != "complete":
        if (backup / relative).exists():
            mismatches.append(f"{relative}: unexpected file in backup")
        return 0
    source = backup / relative
    if not source.exists():
        mismatches.append(f"{relative}: missing in backup")
        return 0
    destination = target / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    if sha256_file(destination) != manifest.get("sha256"):
        mismatches.append(f"{relative}: checksum")
        return 0
    if destination.stat().st_size != int(manifest.get("bytes") or -1):
        mismatches.append(f"{relative}: size")
        return 0
    return destination.stat().st_size
