"""Reference data: documented OpenSky data gaps and processing epochs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

REFERENCE_DIR = Path(__file__).resolve().parents[2] / "configs" / "reference"


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


@dataclass(frozen=True)
class Gap:
    start: datetime
    end: datetime  # exclusive

    def overlaps(self, begin: datetime, finish: datetime) -> bool:
        return begin < self.end and finish > self.start

    def contains(self, begin: datetime, finish: datetime) -> bool:
        return begin >= self.start and finish <= self.end


@dataclass(frozen=True)
class Epoch:
    id: str
    start: datetime | None  # None means "from the beginning"
    note: str


def load_gaps(path: Path | None = None) -> tuple[Gap, ...]:
    raw = yaml.safe_load((path or REFERENCE_DIR / "known_gaps.yaml").read_text())
    return tuple(Gap(_parse(g["start"]), _parse(g["end"])) for g in raw["gaps"])


def load_epochs(path: Path | None = None) -> tuple[Epoch, ...]:
    raw = yaml.safe_load((path or REFERENCE_DIR / "processing_epochs.yaml").read_text())
    epochs = tuple(
        Epoch(e["id"], _parse(e["start"]) if e.get("start") else None, e.get("note", ""))
        for e in raw["epochs"]
    )
    floor = datetime.min.replace(tzinfo=UTC)
    return tuple(sorted(epochs, key=lambda e: (e.start is not None, e.start or floor)))


def hour_gap_status(gaps: tuple[Gap, ...], hour_start: datetime) -> str:
    """Return 'inside', 'overlap' or 'none' for the hour beginning at `hour_start`."""
    hour_end = hour_start + timedelta(hours=1)
    if any(g.contains(hour_start, hour_end) for g in gaps):
        return "inside"
    if any(g.overlaps(hour_start, hour_end) for g in gaps):
        return "overlap"
    return "none"


def hour_epoch_label(epochs: tuple[Epoch, ...], hour_start: datetime) -> tuple[str, bool]:
    """Return (epoch id at the hour start, True if a boundary falls inside the hour)."""
    hour_end = hour_start + timedelta(hours=1)
    current = epochs[0].id
    for epoch in epochs:
        if epoch.start is not None and epoch.start <= hour_start:
            current = epoch.id
    boundary = any(e.start is not None and hour_start < e.start < hour_end for e in epochs)
    return current, boundary
