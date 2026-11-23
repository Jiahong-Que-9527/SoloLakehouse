"""Feature construction under the frozen issue-time cutoff (step 2).

The training contract (design §4): one row per interval with the label
``load_mw``, lag features from completed intervals only, and calendar
fields derived from ``interval_start``. No column may contain a value
observed after the cutoff — features for an interval may only use
observations whose ``interval_end`` is at or before ``interval_start``.

``validate_features`` re-derives every rule from the row itself, so a
supplied future feature (a lag whose source interval ends after the
row's interval) is refused instead of silently trained on.
"""

from datetime import timedelta

from energy_forecast.dataset import TrainingDataset
from energy_forecast.fixture import INTERVAL_MINUTES
from energy_forecast.splits import LAG_INTERVALS, Windows


class FeatureError(ValueError):
    """Raised when feature rows violate the issue-time cutoff or the contract."""


FEATURE_SCHEMA = ["interval_start", "load_mw", "lag_7d_mw", "lag_interval_end", "hour", "weekday"]


def build_features(dataset: TrainingDataset, windows: Windows) -> list[dict]:
    """One feature row per interval whose seven-day lag is readable at the
    issue time; rows without the lag are excluded and must be counted by
    the caller via the dataset metadata (never back-filled)."""
    by_start = {row["interval_start"]: row for row in dataset.rows}
    lag_delta = timedelta(minutes=INTERVAL_MINUTES * LAG_INTERVALS)
    rows = []
    for row in dataset.rows:
        interval_start = row["interval_start"]
        lag_start = interval_start - lag_delta
        source = by_start.get(lag_start)
        # Cutoff: the lagged observation must be complete at the issue time.
        if source is None or source["interval_end"] > interval_start:
            continue
        rows.append(
            {
                "interval_start": interval_start,
                "load_mw": row["load_mw"],
                "lag_7d_mw": source["load_mw"],
                "lag_interval_end": source["interval_end"],
                "hour": interval_start.hour,
                "weekday": interval_start.weekday(),
            }
        )
    return rows


def validate_features(rows: list[dict], dataset: TrainingDataset) -> list[str]:
    """Re-derive the contract from the rows; returns the passed check names.

    Refuses (FeatureError):
    - a feature whose source observation ends after the row's interval
      (the future-feature injection the acceptance test exercises),
    - a lag value that differs from the dataset's value at the lag interval
      (a tampered or stale feature),
    - calendar fields not derived from ``interval_start``,
    - a row whose label is missing or outside the dataset.
    """
    by_start = {row["interval_start"]: row for row in dataset.rows}
    checks: list[str] = []

    def check(name: str, ok: bool, detail: str) -> None:
        if not ok:
            raise FeatureError(f"{name} failed: {detail}")
        checks.append(name)

    seen = set()
    for row in rows:
        interval_start = row["interval_start"]
        key = (row.get("area", "DE"), interval_start)
        if key in seen:
            raise FeatureError(f"duplicate feature row for {interval_start}")
        seen.add(key)

        if row["interval_start"] not in by_start:
            raise FeatureError(f"feature row {interval_start} is not a dataset interval")
        dataset_row = by_start[interval_start]
        if row["load_mw"] != dataset_row["load_mw"]:
            raise FeatureError(f"label for {interval_start} differs from the dataset")

        source_end = row["lag_interval_end"]
        if source_end > interval_start:
            raise FeatureError(
                f"lookahead refused: the lag feature for {interval_start} sources an "
                f"observation ending {source_end}, after the issue time"
            )
        lag_start = interval_start - timedelta(minutes=INTERVAL_MINUTES * LAG_INTERVALS)
        expected = by_start.get(lag_start)
        if expected is None or source_end != expected["interval_end"]:
            raise FeatureError(f"lag source for {interval_start} is not the seven-day interval")
        if row["lag_7d_mw"] != expected["load_mw"]:
            raise FeatureError(f"lag value for {interval_start} differs from the dataset")

        if row["hour"] != interval_start.hour or row["weekday"] != interval_start.weekday():
            raise FeatureError(
                f"calendar fields for {interval_start} are not derived from interval_start"
            )

    check("no_lookahead", True, "every feature sources an observation at or before its issue time")
    check("label_integrity", True, "labels match the training dataset")
    check("value_integrity", True, "lag values match the dataset at the lag interval")
    check("calendar_integrity", True, "calendar fields derive from interval_start")
    return checks


def count_excluded(dataset: TrainingDataset, feature_rows: list[dict]) -> int:
    """Rows whose seasonal lag was not yet readable at the issue time."""
    return len(dataset.rows) - len(feature_rows)
