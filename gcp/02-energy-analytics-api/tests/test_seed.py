"""Task 1.1: the seed fixture matches implementation.md step 1 exactly."""

from datetime import timedelta

from energy_api.seed import LATEST_SEED_RELEASE, RELEASE_SEED


def _rows():
    return [obs for release in RELEASE_SEED for obs in release.observations]


def test_two_releases_with_two_rows():
    assert len(RELEASE_SEED) == 2
    assert len(_rows()) == 2


def test_distinct_values():
    assert {obs.value for obs in _rows()} == {10.0, 12.0}


def test_fixed_area_metric_unit():
    assert {obs.area for obs in _rows()} == {"DE"}
    assert {obs.metric for obs in _rows()} == {"actual_load_mwh"}
    assert {obs.unit for obs in _rows()} == {"MWh"}


def test_quarter_hour_intervals():
    for obs in _rows():
        assert obs.interval_end - obs.interval_start == timedelta(minutes=15)


def test_latest_release_holds_the_12_mwh_row():
    latest = next(r for r in RELEASE_SEED if r.release_id == LATEST_SEED_RELEASE)
    assert [obs.value for obs in latest.observations] == [12.0]


def test_all_datetimes_utc_aware():
    for obs in _rows():
        assert obs.interval_start.utcoffset() == timedelta(0)
        assert obs.interval_end.utcoffset() == timedelta(0)
