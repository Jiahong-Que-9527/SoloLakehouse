"""Frozen windows: ordering, contiguity, holdout role, issue rule."""

from datetime import timedelta

import pytest

from energy_forecast.dataset import build_training_dataset
from energy_forecast.fixture import pinned_release
from energy_forecast.splits import WindowError, datetime_from_iso, freeze_windows


@pytest.fixture()
def dataset():
    rows, release = pinned_release()
    return build_training_dataset(rows, release)


@pytest.fixture()
def frozen(dataset):
    return freeze_windows(dataset)


def test_windows_are_ordered_and_contiguous(frozen):
    windows, _spec = frozen
    assert windows.train_start < windows.train_end_exclusive == windows.validation_start
    assert windows.validation_start < windows.validation_end_exclusive == windows.holdout_start
    assert windows.holdout_start < windows.holdout_end_exclusive


def test_holdout_is_the_last_contiguous_week(frozen):
    windows, _spec = frozen
    assert windows.holdout_end_exclusive - windows.holdout_start == timedelta(days=7)
    assert windows.validation_end_exclusive == windows.holdout_start


def test_windows_stay_inside_the_dataset_window(frozen, dataset):
    windows, _spec = frozen
    assert windows.train_start == datetime_from_iso(dataset.metadata["window_start"])
    assert windows.holdout_end_exclusive == datetime_from_iso(
        dataset.metadata["window_end_exclusive"]
    )


def test_spec_records_the_issue_rule_and_the_untouched_holdout(frozen):
    _windows, spec = frozen
    assert spec["forecast_issue"]["cutoff"] == "interval_end <= interval_start"
    assert "untouched" in spec["holdout"]["role"]
    assert spec["order"].startswith("chronological")


def test_partition_covers_every_interval_exactly_once(frozen, dataset):
    windows, _spec = frozen
    starts = [row["interval_start"] for row in dataset.rows]
    parts = [starts.count(s) for s in starts]
    assert all(count == 1 for count in parts)
    for start in starts:
        assert any(
            windows.contains(which, start) for which in ("train", "validation", "holdout")
        ), f"interval {start} is in no window"


def test_refuses_a_validation_window_without_lag_history(dataset):
    """A manual spec whose validation starts before the seven-day lag is
    readable from the train window is refused by the window validator."""
    from energy_forecast.splits import Windows, validate_windows

    early = Windows(
        train_start=datetime_from_iso("2026-06-08T00:00:00+00:00"),
        train_end_exclusive=datetime_from_iso("2026-06-10T00:00:00+00:00"),
        validation_start=datetime_from_iso("2026-06-10T00:00:00+00:00"),
        validation_end_exclusive=datetime_from_iso("2026-06-17T00:00:00+00:00"),
        holdout_start=datetime_from_iso("2026-06-17T00:00:00+00:00"),
        holdout_end_exclusive=datetime_from_iso("2026-06-24T00:00:00+00:00"),
    )
    with pytest.raises(WindowError, match="seasonal lag"):
        validate_windows(early, dataset)
