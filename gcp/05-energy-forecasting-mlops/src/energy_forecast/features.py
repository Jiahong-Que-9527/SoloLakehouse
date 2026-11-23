"""Feature construction under the frozen issue-time cutoff (steps 2-3).

The training contract (design §4): one row per interval with the label
``load_mw``, lag features from completed intervals only, and calendar
fields derived from ``interval_start``. No column may contain a value
observed after the cutoff — features for an interval may only use
observations whose ``interval_end`` is at or before ``interval_start``.

One lag per elapsed day (1..7 days) gives the candidate a signal beyond
the seasonal lag while every feature stays point-in-time readable.
``validate_features`` re-derives every rule from the row itself, so a
supplied future feature (a lag whose source interval ends after the
row's interval) is refused instead of silently trained on.
"""

from datetime import timedelta

from energy_forecast.dataset import TrainingDataset
from energy_forecast.fixture import INTERVAL_MINUTES
from energy_forecast.splits import LAG_INTERVALS

LAG_DAYS = 7  # the longest lag, in days; shorter lags reuse completed intervals


class FeatureError(ValueError):
    """Raised when feature rows violate the issue-time cutoff or the contract."""


def lag_names() -> list[str]:
    return [f"lag_{k}d_mw" for k in range(1, LAG_DAYS + 1)]


def feature_schema() -> list[str]:
    columns = ["interval_start", "load_mw"]
    for day in range(1, LAG_DAYS + 1):
        columns += [f"lag_{day}d_mw", f"lag_{day}d_source_end"]
    columns += ["hour", "weekday"]
    return columns


def build_features(dataset: TrainingDataset) -> list[dict]:
    """One feature row per interval whose seven-day lag is readable at the
    issue time; rows without the seasonal lag are excluded and must be
    counted by the caller (never back-filled)."""
    by_start = {row["interval_start"]: row for row in dataset.rows}
    lag_delta = timedelta(minutes=INTERVAL_MINUTES * LAG_INTERVALS)
    rows = []
    for row in dataset.rows:
        interval_start = row["interval_start"]
        seasonal_start = interval_start - lag_delta
        seasonal = by_start.get(seasonal_start)
        # Cutoff: the seasonal lag must be complete at the issue time.
        if seasonal is None or seasonal["interval_end"] > interval_start:
            continue
        record = {
            "interval_start": interval_start,
            "load_mw": row["load_mw"],
            "hour": interval_start.hour,
            "weekday": interval_start.weekday(),
        }
        for day in range(1, LAG_DAYS + 1):
            source = by_start[interval_start - timedelta(days=day)]
            if source["interval_end"] > interval_start:
                raise FeatureError(
                    f"lookahead in the dataset itself: the {day}-day lag for "
                    f"{interval_start} sources an observation ending {source['interval_end']}"
                )
            record[f"lag_{day}d_mw"] = source["load_mw"]
            record[f"lag_{day}d_source_end"] = source["interval_end"]
        rows.append(record)
    return rows


def validate_features(rows: list[dict], dataset: TrainingDataset) -> list[str]:
    """Re-derive the contract from the rows; returns the passed check names.

    Refuses (FeatureError):
    - any lag feature whose source observation ends after the row's issue
      time (the future-feature injection the acceptance test exercises),
    - a lag value that differs from the dataset's value at its lag interval
      (a tampered or stale feature),
    - a row whose label is missing or differs from the dataset,
    - calendar fields not derived from ``interval_start``.
    """
    by_start = {row["interval_start"]: row for row in dataset.rows}
    checks: list[str] = []
    for row in rows:
        interval_start = row["interval_start"]
        if interval_start not in by_start:
            raise FeatureError(f"feature row {interval_start} is not a dataset interval")
        dataset_row = by_start[interval_start]
        if row["load_mw"] != dataset_row["load_mw"]:
            raise FeatureError(f"label for {interval_start} differs from the dataset")
        for day in range(1, LAG_DAYS + 1):
            source_end = row[f"lag_{day}d_source_end"]
            if source_end > interval_start:
                raise FeatureError(
                    f"lookahead refused: the {day}-day lag for {interval_start} sources "
                    f"an observation ending {source_end}, after the issue time"
                )
            lag_start = interval_start - timedelta(days=day)
            expected = by_start.get(lag_start)
            if expected is None or source_end != expected["interval_end"]:
                raise FeatureError(
                    f"the {day}-day lag for {interval_start} is not the expected interval"
                )
            if row[f"lag_{day}d_mw"] != expected["load_mw"]:
                raise FeatureError(
                    f"the {day}-day lag value for {interval_start} differs from the dataset"
                )
        if row["hour"] != interval_start.hour or row["weekday"] != interval_start.weekday():
            raise FeatureError(
                f"calendar fields for {interval_start} are not derived from interval_start"
            )
    checks += [
        "no_lookahead",
        "label_integrity",
        "value_integrity",
        "calendar_integrity",
    ]
    return checks


def count_excluded(dataset: TrainingDataset, feature_rows: list[dict]) -> int:
    """Rows whose seasonal lag was not yet readable at the issue time."""
    return len(dataset.rows) - len(feature_rows)
