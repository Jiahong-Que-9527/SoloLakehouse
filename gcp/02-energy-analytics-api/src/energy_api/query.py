"""Query port and in-memory fake (plan Task 1.2).

The port is the only data surface the app knows. Windows are half-open:
``interval_start >= start AND interval_start < end``, ordered by
``interval_start``. One request resolves exactly one release — either
the caller pins ``release_id`` or the port resolves the latest passed
release; responses never mix releases.
"""

from datetime import datetime
from typing import Protocol

from energy_api.model import Observation, Summary
from energy_api.seed import LATEST_SEED_RELEASE, SeedRelease


class QueryPort(Protocol):
    """What the API needs from a data source; the BigQuery adapter is the real one."""

    def resolve_release(self, metric: str) -> str | None:
        """Latest passed release for the metric, or None when not published."""
        ...

    def fetch_observations(
        self,
        metric: str,
        area: str,
        start: datetime,
        end: datetime,
        release_id: str,
    ) -> list[Observation]:
        """Half-open window rows for one release, ordered by interval_start."""
        ...

    def summarize(
        self,
        metric: str,
        area: str,
        start: datetime,
        end: datetime,
        release_id: str,
    ) -> Summary:
        """Count/min/max over the same filter; None bounds when empty."""
        ...


class FakeQueryLayer:
    """In-memory QueryPort over the seed releases; the unit-test data source."""

    def __init__(self, releases: tuple[SeedRelease, ...]) -> None:
        self._rows: list[Observation] = [
            obs for release in releases for obs in release.observations
        ]
        self._latest = LATEST_SEED_RELEASE

    def resolve_release(self, metric: str) -> str | None:
        if any(obs.metric == metric for obs in self._rows):
            return self._latest
        return None

    def fetch_observations(
        self,
        metric: str,
        area: str,
        start: datetime,
        end: datetime,
        release_id: str,
    ) -> list[Observation]:
        selected = [
            obs
            for obs in self._rows
            if obs.metric == metric
            and obs.area == area
            and obs.release_id == release_id
            and start <= obs.interval_start < end
        ]
        return sorted(selected, key=lambda obs: obs.interval_start)

    def summarize(
        self,
        metric: str,
        area: str,
        start: datetime,
        end: datetime,
        release_id: str,
    ) -> Summary:
        rows = self.fetch_observations(metric, area, start, end, release_id)
        if not rows:
            return Summary(count=0, minimum=None, maximum=None, unit="MWh")
        values = [obs.value for obs in rows]
        return Summary(
            count=len(rows),
            minimum=min(values),
            maximum=max(values),
            unit=rows[0].unit,
        )
