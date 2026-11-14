"""Collect a contiguous range of state-vector hours on one connection.

Committed hours are skipped. The run stops on the first hour that does not
commit, and when the duration limit is reached. Either stop leaves the
committed hours in place so the same range can be run again.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta
from typing import Any

from .config import Config, ConfigError
from .fetch import collect_hour, new_run_id
from .util import iso, utc_now


def parse_duration(value: str) -> timedelta:
    """Parse `3h`, `90m`, `30s`, or a number of seconds."""
    text = value.strip().lower()
    if not text:
        raise ConfigError("duration is empty")
    unit = text[-1]
    scale = {"h": 3600, "m": 60, "s": 1}
    number = text[:-1] if unit in scale else text
    try:
        seconds = float(number) * scale.get(unit, 1)
    except ValueError as exc:
        raise ConfigError(f"invalid duration: {value!r}") from exc
    if seconds < 0:
        raise ConfigError(f"invalid duration: {value!r}")
    return timedelta(seconds=seconds)


def iter_hours(start: datetime, until: datetime) -> Iterator[datetime]:
    """Hours from `start` inclusive to `until` exclusive."""
    if until <= start:
        raise ConfigError("until must be after from")
    current = start
    while current < until:
        yield current
        current += timedelta(hours=1)


def collect_range(
    connection: Any,
    cfg: Config,
    start: datetime,
    until: datetime,
    *,
    max_duration: timedelta = timedelta(hours=3),
    pause_seconds: float = 0.5,
    progress: Callable[[str], None] | None = None,
    on_hour: Callable[[dict[str, Any]], None] | None = None,
    clock: Callable[[], float] = time.monotonic,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Collect each pending hour. Returns a summary with `outcome` finished or stopped."""
    last = until - timedelta(hours=1)
    if start.date() < cfg.period.start or last.date() >= cfg.period.end:
        raise ConfigError("range is outside the dataset period")
    moment = now or utc_now()
    run_id = new_run_id(moment)
    started = clock()
    committed = 0
    skipped = 0
    limit = max_duration.total_seconds()

    for hour in iter_hours(start, until):
        if clock() - started >= limit:
            return _summary("stopped", "max_duration", committed, skipped, next_hour=hour)
        result = collect_hour(
            connection,
            cfg,
            hour,
            run_id=run_id,
            pause_seconds=pause_seconds,
            progress=progress,
        )
        if on_hour:
            shown = result if result.get("window_start") else {**result, "window_start": iso(hour)}
            on_hour(shown)
        outcome = result["outcome"]
        if outcome == "committed":
            committed += 1
        elif outcome == "skipped":
            skipped += 1
        else:
            return _summary(
                "stopped",
                "hour_failed",
                committed,
                skipped,
                next_hour=hour,
                error_class=result.get("error_class"),
            )
    return _summary("finished", None, committed, skipped)


def _summary(
    outcome: str,
    reason: str | None,
    committed: int,
    skipped: int,
    *,
    next_hour: datetime | None = None,
    error_class: str | None = None,
) -> dict[str, Any]:
    return {
        "outcome": outcome,
        "reason": reason,
        "committed": committed,
        "skipped": skipped,
        "next_hour": None if next_hour is None else iso(next_hour),
        "error_class": error_class,
    }
