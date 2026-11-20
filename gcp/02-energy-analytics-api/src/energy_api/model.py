"""Value objects for the API read path (plan Task 1.1).

Observations mirror the BigQuery view contract: the G01 observation
columns minus the G01-only provenance column, keyed by release.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Observation:
    interval_start: datetime
    interval_end: datetime
    area: str
    metric: str
    value: float
    unit: str
    release_id: str


@dataclass(frozen=True)
class Summary:
    """Aggregate over one release and window; None bounds for an empty one."""

    count: int
    minimum: float | None
    maximum: float | None
    unit: str
