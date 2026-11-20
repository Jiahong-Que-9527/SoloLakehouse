"""Task 1.2: the fake QueryPort resolves releases and honours half-open windows."""

from datetime import UTC, datetime

from energy_api.query import FakeQueryLayer
from energy_api.seed import RELEASE_SEED


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 6, 8, hour, minute, tzinfo=UTC)


def _layer() -> FakeQueryLayer:
    return FakeQueryLayer(releases=RELEASE_SEED)


def test_full_window_over_latest_release_returns_only_latest_rows():
    rows = _layer().fetch_observations(
        metric="actual_load_mwh",
        area="DE",
        start=_dt(0),
        end=_dt(0, 30),
        release_id="seed-2026-06-08-b",
    )
    assert [obs.value for obs in rows] == [12.0]


def test_explicit_release_returns_that_releases_rows():
    rows = _layer().fetch_observations(
        metric="actual_load_mwh",
        area="DE",
        start=_dt(0),
        end=_dt(0, 30),
        release_id="seed-2026-06-08-a",
    )
    assert [obs.value for obs in rows] == [10.0]


def test_to_is_exclusive_at_the_interval_boundary():
    # Review Focus #1: end == 00:15 excludes the interval *starting* at 00:15.
    assert (
        _layer().fetch_observations(
            metric="actual_load_mwh",
            area="DE",
            start=_dt(0),
            end=_dt(0, 15),
            release_id="seed-2026-06-08-b",
        )
        == []
    )
    rows = _layer().fetch_observations(
        metric="actual_load_mwh",
        area="DE",
        start=_dt(0, 15),
        end=_dt(0, 30),
        release_id="seed-2026-06-08-b",
    )
    assert [obs.value for obs in rows] == [12.0]


def test_rows_are_ordered_by_interval_start():
    rows = _layer().fetch_observations(
        metric="actual_load_mwh",
        area="DE",
        start=_dt(0),
        end=_dt(1),
        release_id="seed-2026-06-08-a",
    )
    assert [obs.interval_start for obs in rows] == sorted(obs.interval_start for obs in rows)


def test_empty_window_gives_empty_list_and_null_bounds_summary():
    window = (_dt(1), _dt(1, 15))
    assert (
        _layer().fetch_observations(
            metric="actual_load_mwh",
            area="DE",
            start=window[0],
            end=window[1],
            release_id="seed-2026-06-08-b",
        )
        == []
    )
    summary = _layer().summarize(
        metric="actual_load_mwh",
        area="DE",
        start=window[0],
        end=window[1],
        release_id="seed-2026-06-08-b",
    )
    assert (summary.count, summary.minimum, summary.maximum, summary.unit) == (
        0,
        None,
        None,
        "MWh",
    )


def test_resolve_release_publishes_only_known_metrics():
    assert _layer().resolve_release("actual_load_mwh") == "seed-2026-06-08-b"
    assert _layer().resolve_release("generation_mix") is None


def test_summary_of_a_single_release_window():
    summary = _layer().summarize(
        metric="actual_load_mwh",
        area="DE",
        start=_dt(0),
        end=_dt(0, 30),
        release_id="seed-2026-06-08-a",
    )
    assert (summary.count, summary.minimum, summary.maximum) == (1, 10.0, 10.0)
