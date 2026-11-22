"""M03 evaluation harness tests: folds, metrics, baselines, report bytes."""

from __future__ import annotations

import shutil
from datetime import date, timedelta

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from charging_forecast.contract import load_config
from charging_forecast.eval import (
    BOOTSTRAP_SEED,
    EMBARGO_DAYS,
    US_HOUR,
    Fold,
    build_folds,
    error_metrics,
    fit_station_median,
    issue_time_us,
    load_demand,
    paired_bootstrap,
    run_baselines,
    seasonal_naive,
    target_hours_us,
    valid_issue_range,
    validate_fold,
)
from charging_forecast.generator import ChargingGenerator
from conftest import TINY_CONFIG, publish_manifest, write_config

# A longer window so the fold plan yields real folds (the shared tiny window
# is too short for MIN_TRAIN_ISSUES); the tariff step (2025-03-10) stays in.
EVAL_WINDOW = {"start": "2025-01-01T00:00:00Z", "end": "2025-04-20T23:00:00Z"}


@pytest.fixture()
def eval_release(tmp_path):
    config_path = write_config(tmp_path / "config.yaml", overrides={"window": EVAL_WINDOW})
    cfg = load_config(config_path)
    release = tmp_path / "release"
    ChargingGenerator(cfg).generate(release)
    publish_manifest(release, cfg)
    return release, cfg, load_demand(release, cfg)


# -- fold plan --------------------------------------------------------------


def test_folds_are_stable_and_respect_embargo():
    folds_a, skipped_a = build_folds(TINY_CONFIG)
    folds_b, skipped_b = build_folds(TINY_CONFIG)
    assert folds_a == folds_b and skipped_a == skipped_b

    v_start, _ = valid_issue_range(TINY_CONFIG)
    for fold in folds_a:
        validate_fold(fold, v_start, EMBARGO_DAYS)
        assert fold.train_last_issue + timedelta(days=1 + EMBARGO_DAYS) <= fold.issue_start
    for a, b in zip(folds_a, folds_a[1:], strict=False):
        assert a.issue_end < b.issue_start  # months in order, no overlap


def test_fold_builder_refuses_embargo_violation():
    v_start, _ = valid_issue_range(TINY_CONFIG)
    bad = Fold(date(2025, 3, 1), date(2025, 3, 31), date(2025, 2, 28))
    with pytest.raises(ValueError, match="embargo violation"):
        validate_fold(bad, v_start, EMBARGO_DAYS)


def test_months_without_training_history_are_skipped():
    folds, skipped = build_folds(TINY_CONFIG)
    assert folds == [] and skipped == ["2025-03"], "the only month lacks 14 train issues"


def test_fold_plan_on_the_eval_window():
    from conftest import TINY_CONFIG as _cfg

    cfg = {**_cfg, "window": EVAL_WINDOW}
    folds, skipped = build_folds(cfg)
    assert skipped == ["2025-01"]
    assert [f"{f.issue_start:%Y-%m}" for f in folds] == ["2025-02", "2025-03", "2025-04"]
    for fold in folds:
        assert fold.train_last_issue + timedelta(days=1 + EMBARGO_DAYS) <= fold.issue_start


# -- metrics ------------------------------------------------------------


def test_metric_definitions_on_a_known_case():
    pred = np.array([[2.0, 4.0], [np.nan, 1.0]])
    label = np.array([[1.0, 2.0], [3.0, 1.0]])
    m = error_metrics(pred, label)
    # finite rows: (2,1), (4,2) and (1,1); the NaN-pred row is excluded
    assert m["n"] == 3 and m["excluded"] == 1
    assert m["mae"] == pytest.approx((1.0 + 2.0 + 0.0) / 3)
    assert m["rmse"] == pytest.approx(np.sqrt((1.0 + 4.0 + 0.0) / 3))
    assert m["smape"] == pytest.approx(100.0 * ((2 / 3) + (4 / 6) + 0.0) / 3)


def test_zero_zero_rows_contribute_zero_smape():
    m = error_metrics(np.array([0.0]), np.array([0.0]))
    assert m["smape"] == 0.0 and m["mae"] == 0.0


# -- paired comparison ------------------------------------------------------


def test_paired_bootstrap_is_seeded_and_identical_errors_cover_zero():
    rng = np.random.default_rng(3)
    errs = rng.normal(10.0, 2.0, 500)
    a = paired_bootstrap(errs, errs.copy())
    b = paired_bootstrap(errs, errs.copy())
    assert a == b  # deterministic per seed
    assert a["ci95"][0] <= 0.0 <= a["ci95"][1]
    assert a["mean_abs_error_diff"] == 0.0


def test_paired_bootstrap_detects_a_worse_model():
    rng = np.random.default_rng(4)
    base = rng.normal(10.0, 1.0, 800)
    worse = base + 1.0  # strictly larger errors
    out = paired_bootstrap(worse, base)
    assert out["mean_abs_error_diff"] == pytest.approx(1.0, abs=0.2)
    assert out["ci95"][0] > 0.0 and out["positive_means_model_a_worse"]


# -- baselines over a release ----------------------------------------------


def test_seasonal_naive_equals_demand_one_week_before(eval_release):
    _release, _cfg, demand = eval_release
    issue_day = date(2025, 3, 15)
    preds, labels = seasonal_naive(demand, issue_day)
    s = demand.stations.index("S001")

    t_us = issue_time_us(issue_day)
    targets = target_hours_us(issue_day)
    hours, values, avail = demand.hours["S001"], demand.values["S001"], demand.avail["S001"]
    for i in (0, 12, 23):
        src = targets[i] - 168 * US_HOUR
        idx = np.searchsorted(hours, src)
        if hours[idx] == src and avail[idx] <= t_us:
            assert preds[s, i] == pytest.approx(values[idx])
    assert np.isfinite(labels[s]).all()  # S001 is visible across the window


def test_median_baseline_uses_only_point_in_time_readable_demand(eval_release):
    release, cfg, demand = eval_release
    fold = Fold(date(2025, 3, 12), date(2025, 3, 18), date(2025, 3, 10))
    fitted = fit_station_median(demand, fold.train_last_issue)

    # Re-fit from a release whose demand AFTER the fitting horizon was
    # altered: the fitted medians must not change.
    tampered = release.parent / "release_tampered"
    if tampered.exists():
        shutil.rmtree(tampered)
    shutil.copytree(release, tampered)
    t_fit_us = issue_time_us(fold.train_last_issue)
    for path in sorted((tampered / "data" / "demand").rglob("*.parquet")):
        table = pq.read_table(path)
        future = np.array(
            np.asarray(table["hour_utc"].cast(pa.int64()).to_pylist(), dtype=np.int64) > t_fit_us
        )
        vals = np.array(table["demand_kwh"].to_pylist())
        vals[future] = 999.0
        table = table.set_column(
            table.schema.get_field_index("demand_kwh"),
            "demand_kwh",
            pa.array(vals, type=pa.float64()),
        )
        pq.write_table(table, path)

    fitted_after = fit_station_median(load_demand(tampered, cfg), fold.train_last_issue)
    for sid in demand.stations:
        a = np.where(np.isnan(fitted[sid]), -1.0, fitted[sid])
        b = np.where(np.isnan(fitted_after[sid]), -1.0, fitted_after[sid])
        assert np.array_equal(a, b), sid


# -- report -----------------------------------------------------------------


def test_report_bytes_are_identical_across_runs(eval_release, tmp_path):
    release, cfg, _demand = eval_release
    out_a, out_b = tmp_path / "rep_a", tmp_path / "rep_b"
    run_baselines(release, cfg, out_a)
    run_baselines(release, cfg, out_b)
    for name in ("baseline-report.json", "baseline-report.md"):
        assert (out_a / name).read_bytes() == (out_b / name).read_bytes(), name


def test_report_records_fold_plan_and_comparison(eval_release, tmp_path):
    release, cfg, _demand = eval_release
    report = run_baselines(release, cfg, tmp_path / "rep")
    assert report["source_release_id"] == cfg["release_id"]
    assert report["fold_plan"]["embargo_days"] == EMBARGO_DAYS
    assert report["fold_plan"]["skipped_months"] == ["2025-01"]
    assert len(report["fold_plan"]["folds"]) == 3
    assert report["paired_comparison"]["seed"] == BOOTSTRAP_SEED
    assert report["paired_comparison"]["resamples"] == 2_000
    for name in ("seasonal_naive", "station_median"):
        assert report["results"][name]["overall"]["n"] > 0
        assert set(report["results"][name]["by_district"]) == {"D1", "D2", "D3"}
        assert len(report["results"][name]["by_hour"]) == 24
