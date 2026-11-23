"""Feature contract: cutoff enforcement and the lookahead refusal."""

from datetime import timedelta

import pytest

from energy_forecast.canonical import canonical_checksum
from energy_forecast.dataset import build_training_dataset
from energy_forecast.features import (
    FeatureError,
    build_features,
    count_excluded,
    validate_features,
)
from energy_forecast.fixture import INTERVAL_MINUTES, pinned_release
from energy_forecast.splits import freeze_windows

LAG_DELTA = timedelta(days=7)  # the seasonal lag: 672 intervals of 15 minutes


@pytest.fixture()
def dataset():
    rows, release = pinned_release()
    return build_training_dataset(rows, release)


@pytest.fixture()
def feature_rows(dataset):
    windows, _spec = freeze_windows(dataset)
    return build_features(dataset, windows)


def test_lag_value_equals_the_dataset_seven_days_earlier(feature_rows, dataset):
    by_start = {row["interval_start"]: row for row in dataset.rows}
    for row in feature_rows[:: 24 * 4]:  # spot-check one interval per day
        expected = by_start[row["interval_start"] - LAG_DELTA]
        assert row["lag_7d_mw"] == expected["load_mw"]
        assert row["lag_interval_end"] == expected["interval_end"]


def test_rows_before_the_lag_exists_are_excluded_and_counted(feature_rows, dataset):
    intervals_per_day = 24 * 60 // INTERVAL_MINUTES
    assert count_excluded(dataset, feature_rows) == 7 * intervals_per_day
    first = feature_rows[0]["interval_start"]
    assert first == dataset.rows[7 * intervals_per_day]["interval_start"]


def test_validation_passes_on_built_features(feature_rows, dataset):
    checks = validate_features(feature_rows, dataset)
    assert checks == [
        "no_lookahead",
        "label_integrity",
        "value_integrity",
        "calendar_integrity",
    ]


def test_future_feature_is_refused(dataset):
    """The acceptance boundary: supplying a future feature must be caught.

    The injected row claims a lag sourced from an observation that ends
    after the row's issue time — exactly what the cutoff forbids.
    """
    windows, _spec = freeze_windows(dataset)
    rows = build_features(dataset, windows)
    injected = [dict(rows[0])]
    injected[0]["lag_interval_end"] = injected[0]["interval_start"] + timedelta(
        minutes=INTERVAL_MINUTES
    )
    with pytest.raises(FeatureError, match="lookahead refused"):
        validate_features(injected, dataset)


def test_tampered_lag_value_is_refused(dataset, feature_rows):
    tampered = [dict(row) for row in feature_rows]
    tampered[0]["lag_7d_mw"] += 1.0
    with pytest.raises(FeatureError, match="differs from the dataset"):
        validate_features(tampered, dataset)


def test_tampered_calendar_field_is_refused(dataset, feature_rows):
    tampered = [dict(row) for row in feature_rows]
    tampered[0]["hour"] = (tampered[0]["hour"] + 1) % 24
    with pytest.raises(FeatureError, match="calendar"):
        validate_features(tampered, dataset)


def test_feature_build_is_deterministic(dataset):
    windows, _spec = freeze_windows(dataset)
    assert canonical_checksum(build_features(dataset, windows)) == canonical_checksum(
        build_features(dataset, windows)
    )
