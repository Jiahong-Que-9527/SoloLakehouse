"""Accept a validated batch and copy it to the backup disk."""

from __future__ import annotations

import getpass
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .batch import Batch
from .config import Config, ConfigError
from .errors import IngestError
from .manifest import read_manifest, sha256_file
from .state import append_event
from .util import iso, utc_now, write_json_atomic


def accept_batch(
    cfg: Config,
    batch: Batch,
    *,
    notes: str = "",
    who: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Record acceptance. A failed batch is refused. Anomalies need a note."""
    root = cfg.paths.data_root
    manifest = _batch_manifest(root, batch)
    if manifest["outcome"] == "failed":
        raise IngestError("BATCH_NOT_VALIDATED")
    if manifest["outcome"] == "review" and not notes.strip():
        raise IngestError("ANOMALIES_NEED_NOTES")
    path = root / "metadata" / "acceptance" / f"{batch.id}.json"
    existing = read_manifest(path)
    if existing is not None:
        existing["outcome"] = "already_accepted"
        return existing
    moment = now or utc_now()
    record = {
        "accepted_at": iso(moment),
        "anomalies": manifest["anomalies"],
        "batch_id": batch.id,
        "notes": notes,
        "outcome": "accepted",
        "validation": manifest["outcome"],
        "who": who or getpass.getuser(),
    }
    write_json_atomic(path, record)
    append_event(
        root, {"at": record["accepted_at"], "batch_id": batch.id, "kind": "batch_accepted"}
    )
    record["path"] = str(path)
    return record


def publish_batch(cfg: Config, batch: Batch, *, now: datetime | None = None) -> dict[str, Any]:
    """Copy an accepted batch to the backup root and verify every checksum."""
    root = cfg.paths.data_root
    acceptance = read_manifest(root / "metadata" / "acceptance" / f"{batch.id}.json")
    if acceptance is None:
        raise IngestError("BATCH_NOT_ACCEPTED")
    manifest = _batch_manifest(root, batch)
    if manifest["outcome"] == "failed":
        raise IngestError("BATCH_NOT_VALIDATED")
    backup = cfg.paths.backup_root
    if not backup.exists():
        if not backup.parent.exists():
            raise IngestError("BACKUP_UNAVAILABLE")
        backup.mkdir(parents=True, exist_ok=True)
    copied = _copy_files(root, backup, manifest)
    _backup_state(root, backup)
    checked, mismatches = _verify(root, backup, copied)
    moment = now or utc_now()
    record = {
        "accepted_at": acceptance["accepted_at"],
        "batch_id": batch.id,
        "checked": checked,
        "copied": len(copied),
        "mismatches": mismatches,
        "outcome": "published" if not mismatches else "failed",
        "published_at": iso(moment),
    }
    if mismatches:
        raise IngestError(f"BACKUP_MISMATCH: {len(mismatches)} files")
    path = root / "metadata" / "published" / f"{batch.id}.json"
    write_json_atomic(path, record)
    write_json_atomic(backup / "metadata" / "published" / f"{batch.id}.json", record)
    append_event(
        root, {"at": record["published_at"], "batch_id": batch.id, "kind": "batch_published"}
    )
    record["path"] = str(path)
    return record


def _batch_manifest(root: Path, batch: Batch) -> dict[str, Any]:
    manifest = read_manifest(root / "metadata" / "manifests" / "batches" / f"{batch.id}.json")
    if manifest is None:
        raise ConfigError(f"batch {batch.id} has not been validated")
    return manifest


def _copy_files(root: Path, backup: Path, manifest: dict[str, Any]) -> list[str]:
    names = [
        f"metadata/manifests/batches/{manifest['batch_id']}.json",
        f"metadata/acceptance/{manifest['batch_id']}.json",
    ]
    for day in manifest["days"]:
        hour_dir = root / "metadata" / "manifests" / "hours" / f"dt={day['date']}"
        if hour_dir.exists():
            names.extend(
                path.relative_to(root).as_posix() for path in sorted(hour_dir.glob("hour-*.json"))
            )
        flight = root / "metadata" / "manifests" / "days" / f"dt={day['date']}" / "flights.json"
        if flight.exists():
            names.append(flight.relative_to(root).as_posix())
    copied = []
    for name in names:
        source = root / name
        if not source.exists():
            continue
        target = backup / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(name)
        manifest_body = read_manifest(source)
        data = None if manifest_body is None else manifest_body.get("path")
        if data and (root / data).exists():
            destination = backup / data
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / data, destination)
            copied.append(data)
    return copied


def _backup_state(root: Path, backup: Path) -> None:
    source = root / "metadata" / "state.db"
    if not source.exists():
        return
    target = backup / "metadata" / "state.db"
    target.parent.mkdir(parents=True, exist_ok=True)
    original = sqlite3.connect(source)
    try:
        copy = sqlite3.connect(target)
        try:
            original.backup(copy)
        finally:
            copy.close()
    finally:
        original.close()


def _verify(root: Path, backup: Path, names: list[str]) -> tuple[int, list[str]]:
    mismatches = []
    checked = 0
    for name in names:
        if not name.endswith(".parquet"):
            continue
        source = root / name
        target = backup / name
        checked += 1
        if not target.exists() or sha256_file(source) != sha256_file(target):
            mismatches.append(name)
        elif source.stat().st_size != target.stat().st_size:
            mismatches.append(name)
    return checked, mismatches
