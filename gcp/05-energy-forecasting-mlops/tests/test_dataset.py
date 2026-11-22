from datetime import timedelta

import pytest

from energy_forecast.dataset import DatasetError, build_training_dataset
from energy_forecast.fixture import Release, pinned_release


def test_metadata_records_the_target_conversion():
    rows, release = pinned_release()
    dataset = build_training_dataset(rows, release)
    target = dataset.metadata["target"]
    assert target["name"] == "load_mw"
    assert "MWh" in target["definition"] and "hours" in target["definition"]
    assert target["source_metric"] == "actual_load_mwh"
    assert target["source_unit"] == "MWh"
    assert target["interval_minutes"] == 15
    assert dataset.metadata["row_count"] == len(rows)
    assert dataset.metadata["release_id"] == release.release_id
    assert dataset.metadata["release_status"] == "passed"


def test_every_training_row_carries_an_average_mw_target():
    rows, release = pinned_release()
    dataset = build_training_dataset(rows, release)
    for row in dataset.rows[::512]:
        assert row["load_mw"] == pytest.approx(row["value"] / 0.25)


def test_window_metadata_spans_the_fixture():
    rows, release = pinned_release()
    dataset = build_training_dataset(rows, release)
    assert dataset.metadata["window_start"] == "2026-06-08T00:00:00+00:00"
    assert dataset.metadata["window_end_exclusive"] == "2026-07-06T00:00:00+00:00"


def test_refuses_a_release_without_a_release_id():
    rows, _ = pinned_release()
    blank = Release(release_id="   ", status="passed", source="fixture")
    with pytest.raises(DatasetError, match="release id"):
        build_training_dataset(rows, blank)


def test_refuses_a_release_that_is_not_passed():
    rows, _ = pinned_release()
    draft = Release(release_id="g05-fixture-v1", status="draft", source="fixture")
    with pytest.raises(DatasetError, match="passed"):
        build_training_dataset(rows, draft)


def test_refuses_duplicate_business_keys():
    rows, release = pinned_release()
    duplicated = [rows[0], *rows]
    with pytest.raises(DatasetError, match="duplicate"):
        build_training_dataset(duplicated, release)


def test_refuses_grid_gaps():
    rows, release = pinned_release()
    gapped = rows[:100] + rows[101:]  # drop one interior interval
    with pytest.raises(DatasetError, match="gap"):
        build_training_dataset(gapped, release)


def test_refuses_non_uniform_interval_length():
    rows, release = pinned_release()
    warped = [dict(rows[0]), *rows[1:]]
    warped[0]["interval_end"] = warped[0]["interval_start"] + timedelta(minutes=30)
    with pytest.raises(DatasetError, match="uniform"):
        build_training_dataset(warped, release)


def test_refuses_an_empty_release():
    _, release = pinned_release()
    with pytest.raises(DatasetError, match="empty"):
        build_training_dataset([], release)
