import math
from datetime import UTC, datetime, timedelta

import pytest

from energy_forecast.target import (
    TargetError,
    average_load_mw,
    interval_duration_hours,
    to_load_mw,
)


def test_ten_mwh_over_a_quarter_hour_is_forty_mw():
    # The plan's canonical example: 10 MWh quarter-hour yields 40 MW.
    assert average_load_mw(10.0, 0.25) == 40.0


def test_one_hour_interval_keeps_magnitude():
    assert average_load_mw(40.0, 1.0) == 40.0


@pytest.mark.parametrize("duration", [0.0, -0.25, float("nan"), float("inf")])
def test_invalid_durations_are_rejected(duration):
    with pytest.raises(TargetError):
        average_load_mw(10.0, duration)


@pytest.mark.parametrize("energy", [float("nan"), float("inf"), -1.0])
def test_invalid_energy_is_rejected(energy):
    with pytest.raises(TargetError):
        average_load_mw(energy, 0.25)


def test_interval_duration_hours_reads_a_quarter_hour():
    start = datetime(2026, 6, 8, 0, 0, tzinfo=UTC)
    assert interval_duration_hours(start, start + timedelta(minutes=15)) == 0.25


def test_zero_length_interval_is_rejected():
    start = datetime(2026, 6, 8, 0, 0, tzinfo=UTC)
    with pytest.raises(TargetError):
        interval_duration_hours(start, start)


def test_to_load_mw_attaches_the_target():
    start = datetime(2026, 6, 8, 0, 0, tzinfo=UTC)
    rows = [
        {
            "interval_start": start,
            "interval_end": start + timedelta(minutes=15),
            "area": "DE",
            "metric": "actual_load_mwh",
            "value": 10.0,
            "unit": "MWh",
        }
    ]
    converted = to_load_mw(rows)
    assert converted[0]["load_mw"] == 40.0
    assert math.isfinite(converted[0]["load_mw"])
