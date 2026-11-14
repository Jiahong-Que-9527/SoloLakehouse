"""Hour manifest paths. The manifest file is the commit marker."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from .util import write_json_atomic

COMMITTED = frozenset({"complete", "empty", "source_gap"})


def hour_parquet_rel(dataset_id: str, version: str, hour: datetime) -> str:
    return (
        f"bronze/opensky/state_vectors/{dataset_id}/{version}/"
        f"dt={hour:%Y-%m-%d}/hour-{hour:%H}.parquet"
    )


def hour_manifest_rel(hour: datetime) -> str:
    return f"metadata/manifests/hours/dt={hour:%Y-%m-%d}/hour-{hour:%H}.json"


def read_manifest(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def write_manifest(path: Path, payload: dict) -> None:
    write_json_atomic(path, payload)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
