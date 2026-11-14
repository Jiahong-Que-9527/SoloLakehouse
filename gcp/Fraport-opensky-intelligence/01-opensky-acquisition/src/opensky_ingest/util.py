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


def fsync_dir(path: Path) -> None:
    """Flush a directory entry so a rename is durable."""
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def parse_utc_day(value: str) -> date:
    """Parse a UTC calendar day. Hour timestamps are rejected."""
    text = str(value)
    if "T" in text:
        raise ValueError(f"expected a date, got a timestamp: {value!r}")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"invalid date: {value!r}") from exc


def parse_utc_hour(value: str) -> datetime:
    """Parse an hour-aligned UTC timestamp. `Z` and offsets are both accepted."""
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"invalid timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    parsed = parsed.astimezone(UTC)
    if parsed.minute or parsed.second or parsed.microsecond:
        raise ValueError(f"timestamp is not on an hour boundary: {value!r}")
    return parsed


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
        fsync_dir(path.parent)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise
