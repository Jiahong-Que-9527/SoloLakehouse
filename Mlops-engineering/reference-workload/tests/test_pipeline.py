"""M05 pipeline tests: idempotence, artifact determinism, manifest lineage,
promotion gate, pin and rollback drill."""

from __future__ import annotations

import json
from datetime import timedelta

import numpy as np
import pytest

from charging_forecast.contract import load_config, sha256_file
from charging_forecast.eval import load_demand, valid_issue_range
from charging_forecast.features import FeatureBuilder, load_training_features
from charging_forecast.generator import ChargingGenerator
from charging_forecast.pipeline import (
    pin_model,
    read_pin,
    run_pipeline,
    step_publish,
    step_train,
    verify_pin,
    write_model_artifact,
)
from charging_forecast.training import (
    GRID as M04_GRID,
)
from charging_forecast.training import (
    RANDOM_SEED,
    build_training_data,
    make_pipeline,
)
from conftest import publish_manifest, write_config

# The full two-year window: the one-year slice starves the model (no 2026
# regimes to exploit — heatwave, tariff ramp tail, late activations), so the
# station-median baseline is unbeatable there; with them the model wins as it
# does on the real data.
EVAL_WINDOW = {"start": "2025-01-01T00:00:00Z", "end": "2026-12-31T23:00:00Z"}
SMALL_GRID = {"learning_rate": [0.1], "max_leaf_nodes": [15], "min_samples_leaf": [10]}


@pytest.fixture(scope="module")
def m05_env(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("m05")
    config_path = write_config(tmp / "config.yaml", overrides={"window": EVAL_WINDOW})
    cfg = load_config(config_path)
    release = tmp / "release"
    ChargingGenerator(cfg).generate(release)
    publish_manifest(release, cfg)
    v_start, v_end = valid_issue_range(cfg)
    features = tmp / "features"
    FeatureBuilder(release, cfg).materialize(v_start, v_end, features)
    return release, cfg, features, v_start, v_end


def _run(m05_env, tmp_path, release_id, *, max_iter, tracking, grid=SMALL_GRID):
    release, cfg, features, v_start, v_end = m05_env
    return run_pipeline(
        release,
        cfg,
        features,
        tmp_path / f"report-{release_id}",
        release_id,
        releases_dir=tmp_path / "releases",
        models_dir=tmp_path / "models",
        tracking_uri=tracking,
        max_iter=max_iter,
        grid=grid,
        sel_train_end=v_start + timedelta(days=510),
        sel_val_start=v_start + timedelta(days=511),
        sel_val_end=v_end,
    )


# -- artifact determinism -------------------------------------------------------


def test_release_artifact_bytes_are_deterministic(m05_env, tmp_path):
    release, cfg, features, v_start, v_end = m05_env
    demand = load_demand(release, cfg)
    table = load_training_features(features, v_start, v_end)
    issue_days = [v_start + timedelta(days=i) for i in range((v_end - v_start).days + 1)]
    data = build_training_data(table, demand, issue_days)
    labeled = np.isfinite(data.y)

    shas = []
    for i in range(2):
        pipe = make_pipeline(
            {"learning_rate": 0.1, "max_leaf_nodes": 15, "min_samples_leaf": 10},
            max_iter=10,
            seed=RANDOM_SEED,
        )
        pipe.fit(data.X.loc[labeled], data.y[labeled])
        _path, entry = write_model_artifact(pipe, tmp_path / f"m{i}", "model-det")
        shas.append(entry["sha256"])
    assert shas[0] == shas[1], "identical fits must serialize to identical bytes"


# -- idempotence ----------------------------------------------------------------


def test_run_pipeline_twice_changes_nothing(m05_env, tmp_path):
    release, cfg, features, *_ = m05_env
    tracking = f"sqlite:///{tmp_path / 'ml.db'}"

    s1 = _run(m05_env, tmp_path, "model-v001", max_iter=300, tracking=tracking)
    assert s1["train"]["reused"] is False
    assert s1["register"]["created"] is True
    assert s1["publish"]["created"] is True

    manifest_path = tmp_path / "releases" / "model-v001" / "manifest.json"
    artifact_path = tmp_path / "models" / "model-v001" / "model.joblib"
    manifest_before = manifest_path.read_bytes()
    artifact_sha_before = sha256_file(artifact_path)

    s2 = _run(m05_env, tmp_path, "model-v001", max_iter=300, tracking=tracking)
    assert s2["features"]["reused"] is True
    assert s2["train"]["reused"] is True
    assert s2["register"]["created"] is False
    assert s2["register"]["version"] == s1["register"]["version"]
    assert s2["publish"]["created"] is False
    assert manifest_path.read_bytes() == manifest_before
    assert sha256_file(artifact_path) == artifact_sha_before


def test_release_manifest_records_lineage(m05_env, tmp_path):
    release, cfg, features, *_ = m05_env
    tracking = f"sqlite:///{tmp_path / 'ml.db'}"
    _run(m05_env, tmp_path, "model-v001", max_iter=300, tracking=tracking)

    manifest = _manifest(tmp_path, "model-v001")
    assert manifest["kind"] == "model"
    assert manifest["model_release_id"] == "model-v001"
    assert manifest["registered_model_name"]
    assert manifest["data_release_id"] == cfg["release_id"]
    assert manifest["feature_release_id"].startswith("feat-")
    assert manifest["source_commit"]
    assert manifest["mlflow_model_version"] >= 1
    assert manifest["source_run_id"]
    assert manifest["metrics"]["model_mae"] < manifest["metrics"]["station_median_mae"]
    artifact = tmp_path / "models" / "model-v001" / "model.joblib"
    assert manifest["artifact"]["sha256"] == sha256_file(artifact)
    assert manifest["protocol"]["n_folds"] >= 1


def test_publish_refuses_a_manifest_collision(m05_env, tmp_path):
    release, cfg, features, v_start, v_end = m05_env
    tracking = f"sqlite:///{tmp_path / 'ml.db'}"
    s1 = _run(m05_env, tmp_path, "model-v001", max_iter=300, tracking=tracking)

    manifest_path = tmp_path / "releases" / "model-v001" / "manifest.json"
    tampered = _manifest(tmp_path, "model-v001")
    tampered["metrics"]["model_mae"] = 0.0
    manifest_path.write_text(
        json.dumps(tampered, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    report, artifact_path, _reused = step_train(
        release,
        cfg,
        features,
        tmp_path / "report-model-v001",
        "model-v001",
        tmp_path / "models",
        tracking_uri=tracking,
        max_iter=300,
        grid=SMALL_GRID,
        sel_train_end=v_start + timedelta(days=510),
        sel_val_start=v_start + timedelta(days=511),
        sel_val_end=v_end,
    )
    with pytest.raises(RuntimeError, match="collision"):
        step_publish(
            release,
            features,
            report,
            artifact_path,
            "model-v001",
            s1["register"],
            releases_dir=tmp_path / "releases",
        )


# -- promotion gate, pin and rollback drill -------------------------------------


def test_pin_gate_rollback_and_refusal(m05_env, tmp_path):
    release, cfg, features, *_ = m05_env
    tracking = f"sqlite:///{tmp_path / 'ml.db'}"
    releases_dir = tmp_path / "releases"
    models_dir = tmp_path / "models"

    with pytest.raises(RuntimeError, match="no pinned release"):
        verify_pin(release, cfg, features, releases_dir=releases_dir, models_dir=models_dir)

    _run(m05_env, tmp_path, "model-v001", max_iter=300, tracking=tracking)
    pin_model("model-v001", releases_dir=releases_dir, tracking_uri=tracking)
    assert read_pin(releases_dir)["model_release_id"] == "model-v001"

    v1_first = verify_pin(
        release,
        cfg,
        features,
        releases_dir=releases_dir,
        models_dir=models_dir,
        out_dir=tmp_path / "verify",
    )
    v1_again = verify_pin(
        release,
        cfg,
        features,
        releases_dir=releases_dir,
        models_dir=models_dir,
        out_dir=tmp_path / "verify",
    )
    assert v1_first["predictions_sha256"] == v1_again["predictions_sha256"]
    assert v1_first["artifact_sha256"] == _manifest(tmp_path, "model-v001")["artifact"]["sha256"]

    # A better candidate promotes; the previous pin is demoted, not deleted.
    # The M04 grid selects the stronger config (lr 0.1 / 63 leaves / min 40,
    # the same winner as on the real data) and lands strictly below model-v001.
    _run(m05_env, tmp_path, "model-v002", max_iter=300, tracking=tracking, grid=M04_GRID)
    pin_model("model-v002", releases_dir=releases_dir, tracking_uri=tracking)
    assert read_pin(releases_dir)["model_release_id"] == "model-v002"

    # Rollback: re-pin the demoted former release; the gate does not apply,
    # and scoring outputs against the restored pin match the earlier bytes.
    result = pin_model("model-v001", releases_dir=releases_dir, tracking_uri=tracking)
    assert result["rollback"] is True
    assert read_pin(releases_dir)["model_release_id"] == "model-v001"
    v1_restored = verify_pin(
        release,
        cfg,
        features,
        releases_dir=releases_dir,
        models_dir=models_dir,
        out_dir=tmp_path / "verify",
    )
    assert v1_restored["predictions_sha256"] == v1_first["predictions_sha256"]

    # A candidate that does not beat the pin is refused; the pin stays.
    # Forged manifest: no registry version exists for model-v003, so the
    # promotion gate applies — no extra training needed to prove the refusal.
    forged = _manifest(tmp_path, "model-v001")
    forged["model_release_id"] = "model-v003"
    forged["metrics"]["model_mae"] = forged["metrics"]["model_mae"] + 0.1
    forged_dir = tmp_path / "releases" / "model-v003"
    forged_dir.mkdir()
    (forged_dir / "manifest.json").write_text(
        json.dumps(forged, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="promotion refused"):
        pin_model("model-v003", releases_dir=releases_dir, tracking_uri=tracking)
    assert read_pin(releases_dir)["model_release_id"] == "model-v001"


# -- helpers --------------------------------------------------------------------


def _manifest(tmp_path, release_id):
    path = tmp_path / "releases" / release_id / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))
