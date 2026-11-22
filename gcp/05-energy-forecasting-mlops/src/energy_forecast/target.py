"""Target construction: average MW from interval energy (step 1).

The prediction target is the average load in MW over the next 15-minute
interval. Source energy stays in MWh; the conversion is recorded in the
training dataset metadata (implementation plan, first delivery: a 10 MWh
quarter-hour yields 40 MW).
"""

import math


class TargetError(ValueError):
    """Raised when an interval cannot be converted to an average MW target."""


def interval_duration_hours(interval_start, interval_end) -> float:
    """Duration of one interval in hours; refuses zero or negative spans."""
    duration = (interval_end - interval_start).total_seconds() / 3600.0
    if duration <= 0:
        raise TargetError(
            f"invalid interval duration: {interval_start} -> {interval_end} ({duration} h)"
        )
    return duration


def average_load_mw(energy_mwh: float, duration_hours: float) -> float:
    """Average MW over an interval: energy (MWh) divided by duration (hours)."""
    if not math.isfinite(duration_hours) or duration_hours <= 0:
        raise TargetError(f"invalid duration: {duration_hours} h")
    if not math.isfinite(energy_mwh):
        raise TargetError(f"non-finite energy: {energy_mwh} MWh")
    if energy_mwh < 0:
        raise TargetError(f"negative energy is not a load measurement: {energy_mwh} MWh")
    return energy_mwh / duration_hours


def to_load_mw(rows: list[dict]) -> list[dict]:
    """Attach ``load_mw`` to metric_observation rows; refuses bad intervals."""
    converted = []
    for row in rows:
        duration = interval_duration_hours(row["interval_start"], row["interval_end"])
        converted.append({**row, "load_mw": average_load_mw(row["value"], duration)})
    return converted
