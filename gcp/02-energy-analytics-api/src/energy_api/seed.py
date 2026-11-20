"""Two small seed releases, exactly as implementation.md step 1 pins them:

DE / actual_load_mwh, known UTC interval boundaries, distinct values
(10 and 12 MWh), quarter-hour intervals, latest release holds the 12 MWh row.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from energy_api.model import Observation

_INTERVAL = timedelta(minutes=15)


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() != timedelta(0):
        message = "seed timestamps must be UTC"
        raise ValueError(message)
    return parsed


def _observation(release_id: str, start: str, value: float) -> Observation:
    interval_start = _utc(start)
    return Observation(
        interval_start=interval_start,
        interval_end=interval_start + _INTERVAL,
        area="DE",
        metric="actual_load_mwh",
        value=value,
        unit="MWh",
        release_id=release_id,
    )


@dataclass(frozen=True)
class SeedRelease:
    release_id: str
    observations: tuple[Observation, ...]


RELEASE_SEED: tuple[SeedRelease, ...] = (
    SeedRelease(
        release_id="seed-2026-06-08-a",
        observations=(_observation("seed-2026-06-08-a", "2026-06-08T00:00:00+00:00", 10.0),),
    ),
    SeedRelease(
        release_id="seed-2026-06-08-b",
        observations=(_observation("seed-2026-06-08-b", "2026-06-08T00:15:00+00:00", 12.0),),
    ),
)

LATEST_SEED_RELEASE = "seed-2026-06-08-b"
