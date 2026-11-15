"""Batch windows and the batch-level validate check.

A batch is one calendar month. Validation reads manifests, which are the
commit markers. It does not query OpenSky.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from . import __version__
from .config import Config, ConfigError
from .fetch import git_commit
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

# An hour this far under the median of the same weekday and hour is listed.
ANOMALY_FRACTION = 0.25
ANOMALY_MIN_MEDIAN = 1000
BATCHES_NAME = "batches.yaml"


@dataclass(frozen=True)
class Batch:
    id: str
    month: str
    state_from: date
    state_until: date
    flights_from: date
    flights_until: date

    def hours(self) -> Iterator[datetime]:
        current = _at(self.state_from)
        end = _at(self.state_until)
        while current < end:
            yield current
            current += timedelta(hours=1)

    def flight_days(self) -> Iterator[date]:
        day = self.flights_from
        while day < self.flights_until:
            yield day
            day += timedelta(days=1)


def batches_path() -> Path:
    return Path(__file__).resolve().parents[2] / "configs" / BATCHES_NAME


def load_batches(path: Path | None = None) -> dict[str, Batch]:
    source = path or batches_path()
    try:
        raw = yaml.safe_load(source.read_text())
    except FileNotFoundError as exc:
        raise ConfigError(f"batch file not found: {source}") from exc
    items = raw.get("batches") if isinstance(raw, dict) else None
    if not isinstance(items, list) or not items:
        raise ConfigError("batches must be a non-empty list")
    found: dict[str, Batch] = {}
    for item in items:
        batch = _batch(item)
        if batch.id in found:
            raise ConfigError(f"duplicate batch id: {batch.id}")
        found[batch.id] = batch
    return found


def get_batch(batch_id: str, path: Path | None = None) -> Batch:
    found = load_batches(path)
    try:
        return found[batch_id]
    except KeyError as exc:
        raise ConfigError(f"unknown batch: {batch_id}") from exc


def validate_batch(cfg: Config, batch: Batch, *, now: datetime | None = None) -> dict[str, Any]:
    """Check every hour and flight day in the batch. Writes the batch manifest."""
    root = cfg.paths.data_root
    problems: list[dict[str, str]] = []
    hours = [_hour(cfg, root, hour, problems) for hour in batch.hours()]
    flights = [_flight(cfg, root, day, problems) for day in batch.flight_days()]
    _extra_files(root, batch, problems)
    anomalies = _anomalies(hours)
    outcome = "failed" if problems else ("review" if anomalies else "passed")
    moment = now or utc_now()
    record = {
        "anomalies": anomalies,
        "batch_id": batch.id,
        "bytes": sum(item["bytes"] for item in hours),
        "checked_at": iso(moment),
        "complete": sum(1 for item in hours if item["status"] == "complete"),
        "days": _days(batch, hours, flights),
        "elapsed_seconds": round(sum(item["elapsed_seconds"] for item in hours), 3),
        "empty": sum(1 for item in hours if item["status"] == "empty"),
        "expected_flights": len(flights),
        "expected_hours": len(hours),
        "failed": sum(1 for item in hours if item["status"] not in COMMITTED),
        "flight_bytes": sum(item["bytes"] for item in flights),
        "flight_rows": sum(item["rows"] for item in flights),
        "flights_complete": sum(1 for item in flights if item["status"] == "complete"),
        "git_commit": git_commit(),
        "month": batch.month,
        "outcome": outcome,
        "problems": problems,
        "processed_bytes": sum(item["processed_bytes"] for item in hours),
        "rehashed": sum(1 for item in hours if item["rehashed"])
        + sum(1 for item in flights if item["rehashed"]),
        "rows": sum(item["rows"] for item in hours),
        "source_gap": sum(1 for item in hours if item["status"] == "source_gap"),
        "tool_version": __version__,
    }
    path = root / "metadata" / "manifests" / "batches" / f"{batch.id}.json"
    write_json_atomic(path, record)
    append_event(
        root,
        {"at": iso(moment), "batch_id": batch.id, "kind": "batch_validated", "outcome": outcome},
    )
    record["path"] = str(path)
    return record


def _batch(item: object) -> Batch:
    if not isinstance(item, dict):
        raise ConfigError("a batch entry must be a mapping")
    try:
        batch = Batch(
            id=str(item["id"]),
            month=str(item["month"]),
            state_from=date.fromisoformat(str(item["state_from"])),
            state_until=date.fromisoformat(str(item["state_until"])),
            flights_from=date.fromisoformat(str(item["flights_from"])),
            flights_until=date.fromisoformat(str(item["flights_until"])),
        )
    except (KeyError, ValueError) as exc:
        raise ConfigError(f"invalid batch entry: {item!r}") from exc
    if batch.state_until <= batch.state_from or batch.flights_until < batch.flights_from:
        raise ConfigError(f"batch {batch.id} has an empty or reversed window")
    return batch


def _at(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


def _hour(
    cfg: Config,
    root: Path,
    hour: datetime,
    problems: list[dict[str, str]],
) -> dict[str, Any]:
    manifest = read_manifest(root / hour_manifest_rel(hour))
    label = iso(hour)
    expected = hour_parquet_rel(cfg.region.id, cfg.region.version, hour)
    return _unit(root, manifest, expected, "hour", label, problems)


def _flight(
    cfg: Config,
    root: Path,
    day: date,
    problems: list[dict[str, str]],
) -> dict[str, Any]:
    manifest = read_manifest(root / flight_manifest_rel(day))
    expected = flight_parquet_rel(cfg.region.airport, cfg.flights.version, day)
    return _unit(root, manifest, expected, "flight", day.isoformat(), problems)


def _unit(
    root: Path,
    manifest: dict | None,
    expected: str,
    kind: str,
    label: str,
    problems: list[dict[str, str]],
) -> dict[str, Any]:
    key = "hour" if kind == "hour" else "day"
    blank = {
        "bytes": 0,
        "elapsed_seconds": 0.0,
        "key": label,
        "processed_bytes": 0,
        "rehashed": False,
        "rows": 0,
        "status": "missing",
    }
    if manifest is None:
        if (root / expected).exists():
            problems.append({key: label, "problem": "orphan"})
        else:
            problems.append({key: label, "problem": "missing_manifest"})
        return blank
    status = str(manifest.get("status"))
    if status not in COMMITTED:
        problems.append({key: label, "problem": "not_committed"})
        return {**blank, "status": status}
    path = manifest.get("path")
    if status != "complete":
        if path or (root / expected).exists():
            problems.append({key: label, "problem": "unexpected_file"})
        return {**blank, "status": status}
    file = root / expected
    if path != expected or not file.exists():
        problems.append({key: label, "problem": "file_missing"})
        return {**blank, "status": status, "rows": int(manifest.get("rows") or 0)}
    digest = sha256_file(file)
    if digest != manifest.get("sha256") or file.stat().st_size != int(manifest.get("bytes") or -1):
        problems.append({key: label, "problem": "checksum"})
    return {
        "bytes": int(manifest.get("bytes") or 0),
        "elapsed_seconds": float(manifest.get("elapsed_seconds") or 0),
        "key": label,
        "processed_bytes": int(manifest.get("processed_bytes") or 0),
        "rehashed": True,
        "rows": int(manifest.get("rows") or 0),
        "status": status,
    }


def _extra_files(root: Path, batch: Batch, problems: list[dict[str, str]]) -> None:
    """A parquet file in a batch day that is not one of that day's hour files."""
    dataset = root / "bronze" / "opensky" / "state_vectors"
    if not dataset.exists():
        return
    allowed = {f"hour-{hour:%H}.parquet" for hour in batch.hours()}
    days = {hour.date() for hour in batch.hours()}
    for version_dir in sorted(dataset.iterdir()):
        if not version_dir.is_dir():
            continue
        for child in sorted(version_dir.iterdir()):
            if not child.is_dir():
                continue
            for day in sorted(days):
                folder = child / f"dt={day.isoformat()}"
                if not folder.exists():
                    continue
                for path in sorted(folder.glob("hour-*.parquet")):
                    if path.name not in allowed:
                        problems.append(
                            {"hour": f"{day.isoformat()}T{path.name}", "problem": "orphan"}
                        )


def _anomalies(hours: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, int], list[tuple[str, int]]] = defaultdict(list)
    for item in hours:
        if item["status"] != "complete":
            continue
        moment = datetime.fromisoformat(item["key"].replace("Z", "+00:00"))
        grouped[(moment.weekday(), moment.hour)].append((item["key"], item["rows"]))
    found = []
    for values in grouped.values():
        if len(values) < 3:
            continue
        ordered = sorted(row for _, row in values)
        median = ordered[len(ordered) // 2]
        if median < ANOMALY_MIN_MEDIAN:
            continue
        limit = median * ANOMALY_FRACTION
        found.extend(
            {"hour": label, "median_rows": median, "rows": rows}
            for label, rows in values
            if rows < limit
        )
    return found


def _days(
    batch: Batch, hours: list[dict[str, Any]], flights: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in hours:
        by_day[item["key"][:10]].append(item)
    flight_by_day = {item["key"]: item for item in flights}
    rows = []
    day = batch.state_from
    while day < batch.state_until:
        items = by_day.get(day.isoformat(), [])
        flight = flight_by_day.get(day.isoformat())
        rows.append(
            {
                "bytes": sum(item["bytes"] for item in items),
                "date": day.isoformat(),
                "elapsed_seconds": round(sum(item["elapsed_seconds"] for item in items), 3),
                "flight_rows": None if flight is None else flight["rows"],
                "flight_status": None if flight is None else flight["status"],
                "hours_complete": sum(1 for item in items if item["status"] == "complete"),
                "hours_expected": len(items),
                "rows": sum(item["rows"] for item in items),
            }
        )
        day += timedelta(days=1)
    extra = batch.flights_until - timedelta(days=1)
    if extra >= batch.state_until and extra.isoformat() in flight_by_day:
        flight = flight_by_day[extra.isoformat()]
        rows.append(
            {
                "bytes": 0,
                "date": extra.isoformat(),
                "elapsed_seconds": 0,
                "flight_rows": flight["rows"],
                "flight_status": flight["status"],
                "hours_complete": 0,
                "hours_expected": 0,
                "rows": 0,
            }
        )
    return rows
