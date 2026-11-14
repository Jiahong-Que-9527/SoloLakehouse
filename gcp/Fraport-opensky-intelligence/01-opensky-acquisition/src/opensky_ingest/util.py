"""Small shared helpers."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def epoch(moment: datetime) -> int:
    return int(moment.astimezone(UTC).timestamp())


def day_epoch(day: date) -> int:
    return epoch(datetime(day.year, day.month, day.day, tzinfo=UTC))


def write_json_atomic(path: Path, payload: object, *, mode: int = 0o644) -> None:
    """Write JSON through a temporary file and rename it into place."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True, default=str)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise
