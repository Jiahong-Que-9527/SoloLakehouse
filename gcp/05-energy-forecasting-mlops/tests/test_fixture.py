from datetime import timedelta

from energy_forecast.fixture import (
    AREA,
    FIXTURE_RELEASE_ID,
    FIXTURE_RELEASE_STATUS,
    INTERVAL_MINUTES,
    METRIC,
    PINNED_SHA256,
    WEEK_START,
    WEEKS,
    fixture_checksum,
    fixture_rows,
    pinned_release,
)


def test_fixture_names_a_passed_release():
    _, release = pinned_release()
    assert release.release_id == FIXTURE_RELEASE_ID
    assert release.release_id.strip()
    assert release.status == FIXTURE_RELEASE_STATUS == "passed"
    assert release.source == "fixture"


def test_fixture_covers_four_aligned_weeks():
    rows = fixture_rows()
    step = timedelta(minutes=INTERVAL_MINUTES)
    assert len(rows) == WEEKS * 7 * 24 * 60 // INTERVAL_MINUTES
    assert rows[0]["interval_start"] == WEEK_START
    assert rows[-1]["interval_end"] == WEEK_START + timedelta(weeks=WEEKS)
    for row in rows:
        assert row["interval_end"] - row["interval_start"] == step
        assert (row["area"], row["metric"], row["unit"]) == (AREA, METRIC, "MWh")


def test_seasonal_lag_exists_from_day_eight():
    # Sufficient history: every interval from day 8 has an observation
    # exactly seven days earlier, so the baseline and lag features exist
    # across the whole usable training and holdout range.
    rows = fixture_rows()
    keys = {(row["area"], row["metric"], row["interval_start"]) for row in rows}
    week = timedelta(days=7)
    first_lagged = WEEK_START + week
    lagged_starts = [row["interval_start"] for row in rows if row["interval_start"] >= first_lagged]
    assert lagged_starts
    for start in lagged_starts:
        assert ("DE", METRIC, start - week) in keys, start


def test_fixture_is_byte_identical_across_replays():
    assert fixture_rows() == fixture_rows()


def test_fixture_values_are_positive_and_shaped():
    rows = fixture_rows()
    values = [row["value"] for row in rows]
    assert min(values) > 0
    assert max(values) > min(values) * 1.2  # a real daily shape, not a flat line


def test_fixture_checksum_matches_the_pin():
    assert fixture_checksum() == PINNED_SHA256
