"""M04 training tests: contract read path, grid selection, MLflow lineage,
report determinism, prediction determinism, baseline cross-check."""

from __future__ import annotations

import json
import shutil
from datetime import date, timedelta

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from mlflow.tracking import MlflowClient

from charging_forecast.contract import issue_time_utc, load_config
from charging_forecast.eval import (
    EMBARGO_DAYS,
    build_folds,
    load_demand,
    run_baselines,
    valid_issue_range,
)
from charging_forecast.features import FeatureBuilder, load_training_features
from charging_forecast.generator import ChargingGenerator
from charging_forecast.training import (
    EXPERIMENT_NAME,
    RANDOM_SEED,
    build_training_data,
    make_pipeline,
    run_model_training,
)
from conftest import publish_manifest, write_config

# The M03 eval window: long enough for real folds, small enough for tests.
EVAL_WINDOW = {"start": "2025-01-01T00:00:00Z", "end": "2025-04-20T23:00:00Z"}
SMALL_GRID = {"learning_rate": [0.1], "max_leaf_nodes": [15], "min_samples_leaf": [10]}
SMALL_KWARGS = dict(
    grid=SMALL_GRID,
    max_iter=25,
    sel_train_end=date(2025, 3, 5),
    sel_val_start=date(2025, 3, 6),
    sel_val_end=date(2025, 3, 31),
    importance_repeats=2,
)


@pytest.fixture(scope="module")
def m04_env(tmp_path_factory):
    """One generated release plus its materialized features, shared by the
    module's tests (generation and materialization are the slow parts)."""
    tmp = tmp_path_factory.mktemp("m04")
    config_path = write_config(tmp / "config.yaml", overrides={"window": EVAL_WINDOW})
    cfg = load_config(config_path)
    release = tmp / "release"
    ChargingGenerator(cfg).generate(release)
    publish_manifest(release, cfg)
    v_start, v_end = valid_issue_range(cfg)
    features = tmp / "features"
    FeatureBuilder(release, cfg).materialize(v_start, v_end, features)
    return release, cfg, features, v_start, v_end


# -- contract read path --------------------------------------------------------


def test_training_rows_carry_issue_stamps(m04_env):
    _release, _cfg, features, v_start, v_end = m04_env
    table = load_training_features(features, v_start, v_end)
    avail = set(table["available_at"].cast(pa.int64()).to_pylist())
    stamps = set()
    day = v_start
    while day <= v_end:
        stamps.add(int(issue_time_utc(day).timestamp() * 1_000_000))
        day += timedelta(days=1)
    assert avail <= stamps
    # Every issue day contributes all 6 stations x 24 target hours.
    assert table.num_rows == len(stamps) * 6 * 24


def test_shifted_stamps_leave_no_training_rows(m04_env, tmp_path):
    _release, _cfg, features, v_start, v_end = m04_env
    shifted = tmp_path / "features_shifted"
    for part in sorted(features.rglob("*.parquet")):
        dest = shifted / part.relative_to(features)
        dest.parent.mkdir(parents=True, exist_ok=True)
        table = pq.read_table(part)
        avail = (
            np.array(table["available_at"].cast(pa.int64()).to_pylist(), dtype=np.int64)
            + 3_600_000_000
        )
        table = table.set_column(
            table.schema.get_field_index("available_at"),
            "available_at",
            pa.array(avail, type=pa.timestamp("us", tz="UTC")),
        )
        pq.write_table(table, dest)
    shutil.copy(features / "manifest.json", shifted / "manifest.json")
    with pytest.raises(ValueError, match="no feature rows stamped"):
        load_training_features(shifted, v_start, v_end)


def test_labels_join_realized_demand(m04_env):
    release, _cfg, features, v_start, v_end = m04_env
    demand = load_demand(release, None)
    issue_days = [v_start + timedelta(days=i) for i in range((v_end - v_start).days + 1)]
    table = load_training_features(features, v_start, v_end)
    data = build_training_data(table, demand, issue_days)
    assert np.isfinite(data.y).all(), "the tiny release has dense demand labels"

    hours = table["hour_utc"].cast(pa.int64()).to_numpy()
    idx = np.searchsorted(demand.hours["S001"], hours[0])
    assert data.y[0] == pytest.approx(demand.values["S001"][idx])
    assert data.station_idx[0] == 0 and data.hour_idx[0] == 0


# -- determinism ---------------------------------------------------------------


def test_predictions_deterministic_given_seed(m04_env):
    release, _cfg, features, v_start, v_end = m04_env
    demand = load_demand(release, None)
    issue_days = [v_start + timedelta(days=i) for i in range((v_end - v_start).days + 1)]
    table = load_training_features(features, v_start, v_end)
    data = build_training_data(table, demand, issue_days)
    mask = np.isfinite(data.y)

    preds = []
    for _ in range(2):
        pipe = make_pipeline(
            {"learning_rate": 0.1, "max_leaf_nodes": 15, "min_samples_leaf": 10},
            max_iter=25,
            seed=RANDOM_SEED,
        )
        pipe.fit(data.X.loc[mask], data.y[mask])
        preds.append(pipe.predict(data.X.iloc[:500]))
    assert np.array_equal(preds[0], preds[1]), "same seed and data must predict identically"


def test_report_bytes_are_identical_across_runs(m04_env, tmp_path):
    release, cfg, features, *_ = m04_env
    out_a, out_b = tmp_path / "a", tmp_path / "b"
    run_model_training(
        release,
        cfg,
        features,
        out_a,
        tracking_uri=f"sqlite:///{tmp_path / 'ml_a.db'}",
        **SMALL_KWARGS,
    )
    run_model_training(
        release,
        cfg,
        features,
        out_b,
        tracking_uri=f"sqlite:///{tmp_path / 'ml_b.db'}",
        **SMALL_KWARGS,
    )
    for name in ("model-report.json", "model-report.md"):
        assert (out_a / name).read_bytes() == (out_b / name).read_bytes(), name


# -- selection and lineage ---------------------------------------------------


def test_selection_picks_the_min_mae_config(m04_env, tmp_path):
    release, cfg, features, *_ = m04_env
    report = run_model_training(
        release,
        cfg,
        features,
        tmp_path / "out",
        tracking_uri=f"sqlite:///{tmp_path / 'ml.db'}",
        **SMALL_KWARGS,
    )
    sel = report["selection"]
    n_configs = np.prod([len(v) for v in SMALL_GRID.values()])
    assert len(sel["results"]) == n_configs
    best = min(sel["results"], key=lambda row: row["val_metrics"]["mae"])
    assert sel["selected_config"] == best["config"]
    assert sel["selected_config"] in [row["config"] for row in sel["results"]]
    assert sel["split"]["train_rows"] > 0 and sel["split"]["val_rows"] > 0


def test_every_mlflow_run_carries_the_lineage_schema(m04_env, tmp_path):
    release, cfg, features, *_ = m04_env
    tracking = f"sqlite:///{tmp_path / 'mlruns.db'}"
    run_model_training(
        release, cfg, features, tmp_path / "out", tracking_uri=tracking, **SMALL_KWARGS
    )

    client = MlflowClient(tracking_uri=tracking)
    exp = client.get_experiment_by_name(EXPERIMENT_NAME)
    assert exp is not None, "the M04 experiment must exist"
    runs = client.search_runs([exp.experiment_id])
    kinds = {r.data.tags["run_kind"] for r in runs}
    assert kinds == {"grid", "protocol"}

    for run in runs:
        tags = run.data.tags
        assert tags["stage"] == "m04"
        assert tags["data_release_id"] == cfg["release_id"]
        assert tags["feature_release_id"].startswith("feat-")
        assert tags["git_sha"]
        fold_plan = json.loads(tags["fold_plan"])
        assert fold_plan["embargo_days"] == EMBARGO_DAYS
        assert fold_plan["n_folds"] >= 1
        if tags["run_kind"] == "grid":
            assert "val_mae" in run.data.metrics
        else:
            assert "mae_model" in run.data.metrics
            artifact_names = {a.path for a in client.list_artifacts(run.info.run_id)}
            assert {"model-report.json", "model-report.md"} <= artifact_names


# -- protocol cross-checks -----------------------------------------------------


def test_protocol_matches_the_m03_baseline_report(m04_env, tmp_path):
    release, cfg, features, *_ = m04_env
    report = run_model_training(
        release,
        cfg,
        features,
        tmp_path / "out",
        tracking_uri=f"sqlite:///{tmp_path / 'ml.db'}",
        **SMALL_KWARGS,
    )
    base = run_baselines(release, cfg, tmp_path / "base")
    assert (
        report["results"]["seasonal_naive"]["overall"]["mae"]
        == base["results"]["seasonal_naive"]["overall"]["mae"]
    )
    assert (
        report["results"]["station_median"]["overall"]["mae"]
        == base["results"]["station_median"]["overall"]["mae"]
    )
    assert [f["issue_start"] for f in report["fold_plan"]["folds"]] == [
        f["issue_start"] for f in base["fold_plan"]["folds"]
    ]
    assert report["fold_plan"]["skipped_months"] == base["fold_plan"]["skipped_months"]

    folds, _skipped = build_folds(cfg)
    assert len(report["fold_plan"]["folds"]) == len(folds)
    acc = report["acceptance"]
    assert isinstance(acc["beats_seasonal_naive"], bool)
    assert isinstance(acc["beats_station_median"], bool)
    for key in ("model_vs_station_median", "model_vs_seasonal_naive"):
        pc = report["paired_comparison"][key]
        assert pc["ci95"][0] <= pc["ci95"][1]
    assert report["feature_importance"], "importance table must not be empty"
    assert {"bias_kwh", "mean_abs_kwh"} <= set(report["residuals"])
