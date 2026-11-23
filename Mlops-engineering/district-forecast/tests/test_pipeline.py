"""Baseline report determinism, the promotion gate and pipeline reuse."""

from __future__ import annotations

import pytest

from district_forecast.baselines import run_baselines
from district_forecast.dataset import build_dataset
from district_forecast.features import build_features
from district_forecast.pipeline import promotion_gate, run_pipeline
from district_forecast.releases import sha256_file


@pytest.fixture()
def workload(source_release, district_cfg, tmp_path):
    """A full district workload on the tiny fixture: dataset, features,
    baselines and one published model release. Returns the source release
    path so the reuse test can rerun the pipeline over the same inputs."""
    root = tmp_path / "workload"
    paths = {
        "dataset": root / "releases/dataset-district/v001",
        "features": root / "data/features",
        "baselines": root / "data/reports/baselines",
        "reports": root / "data/reports/protocol",
        "models": root / "data/models",
        "releases": root / "releases/models-district",
    }
    build_dataset(district_cfg, source_release, paths["dataset"])
    build_features(district_cfg, paths["dataset"], paths["features"])
    run_baselines(district_cfg, paths["dataset"], paths["baselines"])
    result = run_pipeline(district_cfg, source_release, paths)
    return district_cfg, paths, source_release, result


def test_baseline_report_is_deterministic(source_release, district_cfg, tmp_path):
    derived = tmp_path / "derived"
    build_dataset(district_cfg, source_release, derived)
    first, second = tmp_path / "b1", tmp_path / "b2"
    run_baselines(district_cfg, derived, first)
    run_baselines(district_cfg, derived, second)
    for name in ("baseline-report.json", "baseline-report.md"):
        assert sha256_file(first / name) == sha256_file(second / name)


def test_baseline_report_folds_skip_empty_month(district_cfg, source_release, tmp_path):
    derived = tmp_path / "derived"
    build_dataset(district_cfg, source_release, derived)
    report = run_baselines(district_cfg, derived, tmp_path / "b")
    assert "2025-01" in report["fold_plan"]["skipped_months"]
    assert len(report["fold_plan"]["folds"]) == 7  # February through August


def test_pipeline_publishes_when_the_candidate_beats_baselines(workload):
    _cfg, paths, _source, result = workload
    assert result["reused"] is False
    metrics = result["manifest"]["metrics"]
    gate = result["manifest"]["gate"]
    assert metrics["mae"] < min(gate["baselines"].values())
    assert (paths["releases"] / result["release_id"] / "manifest.json").exists()


def test_pipeline_rerun_reuses_every_step(workload):
    cfg, paths, source, first = workload
    second = run_pipeline(cfg, source, paths)
    assert second["reused"] is True
    assert second["dataset_reused"] and second["features_reused"]
    assert second["baselines_reused"] and second["training_reused"]
    first_sha = sha256_file(paths["releases"] / first["release_id"] / "manifest.json")
    second_sha = sha256_file(paths["releases"] / second["release_id"] / "manifest.json")
    assert first_sha == second_sha


def test_promotion_gate_refuses_a_weak_candidate():
    protocol = {"candidate_id": "model-district-weak", "pooled": {"mae": 9.0}}
    baselines = {
        "results": {
            "district_seasonal_naive": {"overall": {"mae": 5.0}},
            "district_median": {"overall": {"mae": 6.0}},
        }
    }
    with pytest.raises(ValueError, match="refused candidate model-district-weak"):
        promotion_gate(protocol, baselines)


def test_promotion_gate_requires_both_baselines():
    protocol = {"candidate_id": "m", "pooled": {"mae": 5.0}}
    baselines = {
        "results": {
            "district_seasonal_naive": {"overall": {"mae": 5.0}},
            "district_median": {"overall": {"mae": 4.0}},
        }
    }
    with pytest.raises(ValueError, match="district_seasonal_naive"):
        promotion_gate(protocol, baselines)
