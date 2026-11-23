"""Window freezing and the forecast issue rule (implementation step 2).

Freezes the chronological train/validation/holdout windows for the pinned
fixture and records the forecast issue convention (design §1 split and
cutoff decisions):

- Time ordered, rows are never shuffled; the holdout is the last
  contiguous part of the window and is untouched by any selection.
- Features for an interval may only use observations whose
  ``interval_end`` is at or before that interval's start (the issue time).
- Train and validation windows must leave enough history for the
  seven-day seasonal lag; rows before the lag exists are excluded
  downstream and counted, never back-filled.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from energy_forecast.dataset import TrainingDataset
from energy_forecast.fixture import INTERVAL_MINUTES

LAG_INTERVALS = 7 * 24 * 60 // INTERVAL_MINUTES  # the seven-day seasonal lag


class WindowError(ValueError):
    """Raised when a window freeze is refused."""


@dataclass(frozen=True)
class Windows:
    """The frozen split; datetimes are interval starts, ends exclusive."""

    train_start: datetime
    train_end_exclusive: datetime
    validation_start: datetime
    validation_end_exclusive: datetime
    holdout_start: datetime
    holdout_end_exclusive: datetime
    lag_intervals: int = LAG_INTERVALS

    def contains(self, which: str, interval_start) -> bool:
        start = getattr(self, f"{which}_start")
        end = getattr(self, f"{which}_end_exclusive")
        return start <= interval_start < end


def freeze_windows(dataset: TrainingDataset) -> tuple[Windows, dict]:
    """Freeze the split: last week holdout, the week before it validation,
    everything earlier trains. Refuses a window too short for the split."""
    window_start = datetime_from_iso(dataset.metadata["window_start"])
    window_end_exclusive = datetime_from_iso(dataset.metadata["window_end_exclusive"])
    span = window_end_exclusive - window_start
    holdout_span = 7 * timedelta(days=1)
    validation_span = 7 * timedelta(days=1)
    if span < holdout_span + validation_span + 7 * timedelta(days=1):
        raise WindowError(
            f"window {span} is too short for train + validation + holdout "
            "(each needs at least the seven-day seasonal history)"
        )

    holdout_start = window_end_exclusive - holdout_span
    validation_start = holdout_start - validation_span
    train_start = window_start
    windows = Windows(
        train_start=train_start,
        train_end_exclusive=validation_start,
        validation_start=validation_start,
        validation_end_exclusive=holdout_start,
        holdout_start=holdout_start,
        holdout_end_exclusive=window_end_exclusive,
    )
    validate_windows(windows, dataset)

    spec = {
        "order": "chronological; rows are never shuffled (design §1)",
        "train": {
            "start": windows.train_start.isoformat(),
            "end_exclusive": windows.train_end_exclusive.isoformat(),
        },
        "validation": {
            "start": windows.validation_start.isoformat(),
            "end_exclusive": windows.validation_end_exclusive.isoformat(),
        },
        "holdout": {
            "start": windows.holdout_start.isoformat(),
            "end_exclusive": windows.holdout_end_exclusive.isoformat(),
            "role": "untouched final evaluation; no selection may read it",
        },
        "forecast_issue": {
            "rule": "features for an interval may only use observations "
            "whose interval_end is at or before that interval's start",
            "cutoff": "interval_end <= interval_start",
            "lag_intervals": LAG_INTERVALS,
            "excluded_rows": "rows whose seasonal lag is not yet readable are "
            "excluded and counted, never back-filled",
        },
    }
    return windows, spec


def validate_windows(windows: Windows, dataset: TrainingDataset) -> None:
    """Refuse overlapping, unordered or degenerate windows."""
    if not (
        windows.train_start
        < windows.train_end_exclusive
        <= windows.validation_start
        < windows.validation_end_exclusive
        <= windows.holdout_start
        < windows.holdout_end_exclusive
    ):
        raise WindowError(f"windows must be ordered and contiguous, got {windows}")
    window_start = datetime_from_iso(dataset.metadata["window_start"])
    window_end_exclusive = datetime_from_iso(dataset.metadata["window_end_exclusive"])
    if windows.train_start < window_start or windows.holdout_end_exclusive > window_end_exclusive:
        raise WindowError("windows must stay inside the dataset window")
    # The lag must exist for validation rows: the validation start needs at
    # least lag_intervals of history inside the train window.
    if (windows.validation_start - windows.train_start) < timedelta(
        minutes=INTERVAL_MINUTES * windows.lag_intervals
    ):
        raise WindowError(
            "the validation window starts before the seven-day seasonal lag "
            "is readable from the train window"
        )


def datetime_from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)
