"""Training dataset build: release refusals, grid validation, metadata (step 1).

Builds the training rows from a release's metric observations and refuses
anything the design forbids (design §5): a release without an id, a
release whose status is not ``passed``, duplicate business keys, and a
grid with gaps, overlaps or non-uniform interval lengths — the seven-day
seasonal lag of the baseline needs a uniform 15-minute grid.
"""

from dataclasses import dataclass
from datetime import timedelta

from energy_forecast.canonical import canonical_checksum
from energy_forecast.fixture import INTERVAL_MINUTES, METRIC, UNIT, Release
from energy_forecast.target import to_load_mw


class DatasetError(ValueError):
    """Raised when a release or its grid is refused for training."""


@dataclass(frozen=True)
class TrainingDataset:
    """Training rows (each with ``load_mw``) plus the recorded metadata."""

    rows: list[dict]
    metadata: dict


def build_training_dataset(rows: list[dict], release: Release) -> TrainingDataset:
    """Validate the release and its grid, convert the target, record metadata."""
    if not release.release_id or not release.release_id.strip():
        raise DatasetError("refusing a release that does not name a release id (design §5)")
    if release.status != "passed":
        raise DatasetError(
            f"refusing release {release.release_id!r} with status {release.status!r}; "
            "only a 'passed' release may train (design §5)"
        )
    if not rows:
        raise DatasetError("refusing an empty release")

    seen = set()
    for row in rows:
        key = (row["area"], row["metric"], row["interval_start"])
        if key in seen:
            raise DatasetError(f"duplicate business key: {key}")
        seen.add(key)

    step = timedelta(minutes=INTERVAL_MINUTES)
    starts = sorted(key[2] for key in seen)
    for row in rows:
        if row["interval_end"] - row["interval_start"] != step:
            raise DatasetError(
                f"interval at {row['interval_start']} is not a uniform "
                f"{INTERVAL_MINUTES}-minute interval"
            )
    for previous, current in zip(starts, starts[1:], strict=False):
        if current - previous != step:
            raise DatasetError(f"grid gap or irregular spacing between {previous} and {current}")

    converted = to_load_mw(rows)
    metadata = {
        "release_id": release.release_id,
        "release_status": release.status,
        "release_source": release.source,
        "target": {
            "name": "load_mw",
            "definition": (
                "average MW over the interval = interval energy (MWh) / interval duration (hours)"
            ),
            "source_metric": METRIC,
            "source_unit": UNIT,
            "interval_minutes": INTERVAL_MINUTES,
        },
        "row_count": len(converted),
        "window_start": starts[0].isoformat(),
        "window_end_exclusive": (starts[-1] + step).isoformat(),
        "input_sha256": canonical_checksum(rows),
    }
    return TrainingDataset(rows=converted, metadata=metadata)
