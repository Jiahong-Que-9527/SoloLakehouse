"""Baseline vs candidate: the frozen comparison and its report."""

import pytest

from energy_forecast.canonical import canonical_checksum
from energy_forecast.dataset import build_training_dataset
from energy_forecast.evaluation import (
    LOSING_CANDIDATE_CONFIG,
    REPLAY_TOLERANCE_MW,
    run_evaluation,
    seasonal_naive_predictions,
)
from energy_forecast.features import build_features
from energy_forecast.fixture import losing_release, pinned_release
from energy_forecast.splits import freeze_windows


@pytest.fixture()
def eval_bundle():
    rows, release = pinned_release()
    dataset = build_training_dataset(rows, release)
    windows, spec = freeze_windows(dataset)
    features = build_features(dataset)
    report, model, predictions = run_evaluation(dataset, windows, features, git_sha="test-sha")
    return dataset, windows, features, report, model, predictions


def test_baseline_predictions_are_the_seasonal_lag(eval_bundle):
    _dataset, _windows, features, _report, _model, _preds = eval_bundle
    naive = seasonal_naive_predictions(features)
    assert naive[0] == features[0]["lag_7d_mw"]


def test_candidate_beats_the_baseline_on_the_frozen_holdout(eval_bundle):
    _dataset, _windows, _features, report, _model, _preds = eval_bundle
    assert report["holdout"]["candidate"]["mae_mw"] <= report["holdout"]["baseline"]["mae_mw"]


def test_report_records_the_required_fields(eval_bundle):
    _dataset, windows, _features, report, _model, _preds = eval_bundle
    assert report["git_sha"] == "test-sha"
    assert report["candidate"]["library"] == "lightgbm"
    assert report["candidate"]["config"]["seed"] == 20261123
    assert report["windows"]["holdout"]["start"] == windows.holdout_start.isoformat()
    assert report["replay_tolerance_mw"] == REPLAY_TOLERANCE_MW
    assert report["holdout"]["baseline"]["n"] == report["holdout"]["candidate"]["n"] > 0


def test_report_is_deterministic_across_replays(eval_bundle):
    dataset, windows, features, report, _model, _preds = eval_bundle
    replay, _model2, _preds2 = run_evaluation(dataset, windows, features, git_sha="test-sha")
    assert canonical_checksum(report) == canonical_checksum(replay)
    assert (
        abs(report["holdout"]["candidate"]["mae_mw"] - replay["holdout"]["candidate"]["mae_mw"])
        <= REPLAY_TOLERANCE_MW
    )


def test_the_deliberately_losing_candidate_loses():
    """The gate drill: the underfit candidate on the separate noise fixture
    loses to the baseline, so the promotion gate has something to refuse."""
    rows, release = losing_release()
    dataset = build_training_dataset(rows, release)
    windows, _spec = freeze_windows(dataset)
    features = build_features(dataset)
    report, _model, _preds = run_evaluation(
        dataset, windows, features, git_sha="drill", candidate_config=LOSING_CANDIDATE_CONFIG
    )
    assert report["holdout"]["candidate"]["mae_mw"] > report["holdout"]["baseline"]["mae_mw"]
    assert report["candidate"]["config"]["num_boost_round"] == 1
