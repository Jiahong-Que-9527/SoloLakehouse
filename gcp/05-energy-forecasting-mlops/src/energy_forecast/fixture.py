"""Deterministic synthetic release fixture (implementation sequence step 1).

The rows mirror the G01 ``metric_observation`` schema (interval_start,
interval_end, area, metric, value, unit, release_id) so the training
dataset build is identical for a real passed G04 release and for this
fixture (G01 design §5.4: downstream projects ship a fixture with the
same schema). The energy values are a pure integer-arithmetic waveform —
no libm calls, no RNG — so every replay produces byte-identical rows and
the build is pinned by the recorded canonical checksum.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from energy_forecast.canonical import canonical_checksum

INTERVAL_MINUTES = 15
INTERVALS_PER_DAY = 24 * 60 // INTERVAL_MINUTES
AREA = "DE"
METRIC = "actual_load_mwh"
UNIT = "MWh"

FIXTURE_RELEASE_ID = "g05-fixture-v1"
FIXTURE_RELEASE_STATUS = "passed"

# Four aligned weeks from the G01/G04 anchor Monday: weeks 1-3 carry
# train/validation rows, week 4 is held out, and the seven-day seasonal
# lag exists for every interval from day 8 onward.
WEEK_START = datetime(2026, 6, 8, 0, 0, tzinfo=UTC)
WEEKS = 4

BASE_MWH = 10.5
MIDDAY_PEAK_MWH = 3.2
EVENING_PEAK_MWH = 1.0
WEEKEND_DIP_MWH = 0.9
WIGGLE_MWH = 0.15


@dataclass(frozen=True)
class Release:
    """Release descriptor; a real G04 release fills this from its record."""

    release_id: str
    status: str
    source: str


def pinned_release() -> tuple[list[dict], Release]:
    """The pinned fixture with its release descriptor."""
    return fixture_rows(), Release(
        release_id=FIXTURE_RELEASE_ID, status=FIXTURE_RELEASE_STATUS, source="fixture"
    )


def fixture_rows() -> list[dict]:
    """One observation per 15-minute interval for four aligned weeks."""
    step = timedelta(minutes=INTERVAL_MINUTES)
    interval_count = WEEKS * 7 * INTERVALS_PER_DAY
    rows = []
    for index in range(interval_count):
        interval_start = WEEK_START + step * index
        rows.append(
            {
                "interval_start": interval_start,
                "interval_end": interval_start + step,
                "area": AREA,
                "metric": METRIC,
                "value": interval_energy_mwh(index),
                "unit": UNIT,
                "release_id": FIXTURE_RELEASE_ID,
            }
        )
    return rows


def interval_energy_mwh(index: int) -> float:
    """Quarter-hour energy in MWh; a pure function of the interval index."""
    phase = index % INTERVALS_PER_DAY
    day = index // INTERVALS_PER_DAY
    weekday = day % 7
    midday = _triangle(phase - 44, INTERVALS_PER_DAY)  # peak 11:00 UTC
    evening = _triangle(phase - 76, INTERVALS_PER_DAY // 2)  # peaks 19:00 and 07:00 UTC
    weekend = WEEKEND_DIP_MWH if weekday >= 5 else 0.0
    wiggle = WIGGLE_MWH * (((index * 73) % 19) / 19 - 0.5)
    return round(
        BASE_MWH + MIDDAY_PEAK_MWH * midday + EVENING_PEAK_MWH * evening - weekend + wiggle, 6
    )


def _triangle(offset: int, period: int) -> float:
    """1.0 at offset 0, falling linearly to 0.0 at +/- period/2."""
    distance = abs(offset) % period
    distance = min(distance, period - distance)
    return 1 - 2 * distance / period


def fixture_checksum(rows: list[dict] | None = None) -> str:
    """Canonical checksum of the fixture rows."""
    return canonical_checksum(rows if rows is not None else fixture_rows())


# Recorded pin: the checksum must stay stable unless the fixture is
# deliberately re-pinned under a new release id (design §5 replay rule).
PINNED_SHA256 = "f4d1f4d86f74721f3147c25d6879ad73dc00ad352025f3a2ffb4fd7013dae4f8"
