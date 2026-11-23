"""The promotion gate: registration, refusal, and the release manifest."""

import json

import mlflow
import pytest

from energy_forecast.dataset import build_training_dataset
from energy_forecast.evaluation import LOSING_CANDIDATE_CONFIG, run_evaluation
from energy_forecast.features import build_features
from energy_forecast.fixture import losing_release, pinned_release
from energy_forecast.registry import (
    REGISTRY_MODEL_NAME,
    PromotionRefused,
    promote_candidate,
    refuse_losing_candidate,
    register_baseline,
)
from energy_forecast.splits import freeze_windows


@pytest.fixture()
def good_bundle(tmp_path):
    rows, release = pinned_release()
    dataset = build_training_dataset(rows, release)
    windows, _spec = freeze_windows(dataset)
    features = build_features(dataset)
    report, model, _preds = run_evaluation(dataset, windows, features, git_sha="reg-test")
    return dataset, report, model, tmp_path / "mlflow"


def test_gate_promotes_and_publishes_a_traceable_manifest(good_bundle, tmp_path):
    dataset, report, model, tracking_dir = good_bundle
    baseline = register_baseline(dataset, report, model, tracking_dir, git_sha="reg-test")
    promotion = promote_candidate(dataset, report, model, tracking_dir, tmp_path / "releases")
    assert promotion.stage == "promoted"
    assert promotion.model_version == baseline.model_version + 1

    manifest = json.loads((tmp_path / "releases" / "model-manifest.json").read_text())
    assert manifest["release_id"] == dataset.metadata["release_id"]
    assert manifest["input_sha256"] == dataset.metadata["input_sha256"]
    assert manifest["git_sha"] == "reg-test"
    assert manifest["mlflow_run_id"] == promotion.run_id
    assert manifest["gate"]["decision"] == "promoted"
    assert (
        manifest["holdout_metrics"]["candidate"]["mae_mw"]
        <= manifest["holdout_metrics"]["baseline"]["mae_mw"]
    )


def test_registry_holds_two_versions_after_promotion(good_bundle):
    dataset, report, model, tracking_dir = good_bundle
    register_baseline(dataset, report, model, tracking_dir, git_sha="reg-test")
    promote_candidate(dataset, report, model, tracking_dir, tracking_dir.parent / "releases")
    client = mlflow.tracking.MlflowClient(tracking_uri=f"sqlite:///{tracking_dir / 'mlflow.db'}")
    versions = client.search_model_versions(f"name='{REGISTRY_MODEL_NAME}'")
    assert {int(v.version) for v in versions} == {1, 2}


def test_gate_refuses_the_deliberately_losing_candidate(tmp_path):
    rows, release = losing_release()
    dataset = build_training_dataset(rows, release)
    windows, _spec = freeze_windows(dataset)
    features = build_features(dataset)
    report, model, _preds = run_evaluation(
        dataset, windows, features, git_sha="drill", candidate_config=LOSING_CANDIDATE_CONFIG
    )
    with pytest.raises(PromotionRefused, match="refused the candidate"):
        promote_candidate(dataset, report, model, tmp_path / "mlflow", tmp_path / "releases")

    refusal = refuse_losing_candidate(release, report, tmp_path / "mlflow")
    assert refusal["decision"] == "refused"
    assert refusal["registry_version"] is None
    # The refused run stays queryable as an experiment.
    client = mlflow.tracking.MlflowClient(
        tracking_uri=f"sqlite:///{tmp_path / 'mlflow' / 'mlflow.db'}"
    )
    run = client.get_run(refusal["run_id"])
    assert run.data.tags["experiment_only"] == "true"
    versions = client.search_model_versions(f"name='{REGISTRY_MODEL_NAME}'")
    assert versions == []


def test_gate_refusal_message_carries_the_numbers(tmp_path):
    rows, release = losing_release()
    dataset = build_training_dataset(rows, release)
    windows, _spec = freeze_windows(dataset)
    features = build_features(dataset)
    report, model, _preds = run_evaluation(
        dataset, windows, features, git_sha="drill", candidate_config=LOSING_CANDIDATE_CONFIG
    )
    with pytest.raises(PromotionRefused) as excinfo:
        promote_candidate(dataset, report, model, tmp_path / "mlflow", tmp_path / "releases")
    message = str(excinfo.value)
    assert str(report["holdout"]["candidate"]["mae_mw"]) in message
    assert str(report["holdout"]["baseline"]["mae_mw"]) in message
