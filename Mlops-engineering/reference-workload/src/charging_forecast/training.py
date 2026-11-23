"""Supervised model development under experiment discipline (M04).

Implements the resolved M04 decisions (docs/delivery-plan.md, M04 entry):
the candidate is a sklearn HistGradientBoostingRegressor behind a
ColumnTransformer pipeline — chosen over LightGBM because its fits are
deterministic given a fixed seed and a single OpenMP thread, so committed
reports stay byte-reproducible. Search is a fixed seeded grid
(learning_rate x max_leaf_nodes x min_samples_leaf) selected on one internal
split (train issues through 2026-08-31, validation September 2026); early
stopping is off and the iteration budget fixed. The winning config then runs
the M03 fold protocol — the same monthly rolling-origin folds, embargo and
metric suite — against both baselines on identical rows, and every run is
tracked to MLflow with the lineage tag schema (data release, feature
release, git SHA, fold plan).

The model report carries no wall-clock values and no MLflow run IDs: the
same inputs render the same bytes, so the committed report is reproducible
from the release IDs and parameters; run IDs live in the evidence record.

Training rows are read only through features.load_training_features (the
contract's one read path, batched), labels join realized demand at
(station_id, hour_utc), and rows with an unreadable label are excluded from
fitting and scored as excluded by the metric suite — the same finite-mask
rule the baselines use, so all three models are compared on identical rows.
"""

from __future__ import annotations

import os

os.environ.setdefault("OMP_NUM_THREADS", "1")  # before sklearn loads: pin threads for determinism

import json
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import product
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
import pyarrow as pa
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from .contract import git_commit, issue_time_utc, sha256_file
from .eval import (
    EMBARGO_DAYS,
    MEDIAN_WINDOW_DAYS,
    MIN_TRAIN_ISSUES,
    DemandTable,
    build_folds,
    error_metrics,
    fit_station_median,
    load_demand,
    paired_bootstrap,
    seasonal_naive,
    segment_metrics,
    station_median_predictions,
    valid_issue_range,
)
from .features import load_training_features

MODEL_REPORT_SCHEMA_VERSION = "charging-model-report-v1"
EXPERIMENT_NAME = "charging-forecast-m04"
# The filesystem store is in maintenance mode in current MLflow; the sqlite
# backend is the supported local store (gitignored) and keeps M05's registry
# options open.
DEFAULT_TRACKING_URI = "sqlite:///mlruns.db"

RANDOM_SEED = 20261122
MAX_ITER = 300
GRID: dict[str, list] = {
    "learning_rate": [0.05, 0.1],
    "max_leaf_nodes": [31, 63],
    "min_samples_leaf": [20, 40],
}
SEL_TRAIN_END = date(2026, 8, 31)
SEL_VAL_START = date(2026, 9, 1)
SEL_VAL_END = date(2026, 9, 30)
IMPORTANCE_REPEATS = 5
IMPORTANCE_MAX_ROWS = 20_000
TARGET_HOURS = 24

CAT_FEATURES = ["district", "poi_category"]
NUM_FEATURES = [
    "hour_of_day",
    "day_of_week",
    "capacity_kw",
    "days_active",
    "demand_lag_24h",
    "demand_lag_168h",
    "demand_rolling_7d_mean",
    "demand_latest",
    "fcst_temperature_c",
    "fcst_precipitation_mm",
    "price_current",
    "price_at_target",
    "event_boost",
]
BIN_FEATURES = ["is_public_holiday", "is_school_break", "is_event_active"]
FEATURE_COLUMNS = CAT_FEATURES + NUM_FEATURES + BIN_FEATURES


def _round(x: float) -> float:
    return round(float(x), 6)


def make_pipeline(params: dict, *, max_iter: int = MAX_ITER, seed: int = RANDOM_SEED) -> Pipeline:
    """The candidate pipeline: one-hot categoricals, passthrough numerics
    (HistGradientBoosting handles NaN natively — no imputation), fixed
    iteration budget with early stopping off."""
    pre = ColumnTransformer(
        [
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CAT_FEATURES),
            ("num", "passthrough", NUM_FEATURES + BIN_FEATURES),
        ]
    )
    model = HistGradientBoostingRegressor(
        early_stopping=False, max_iter=max_iter, random_state=seed, **params
    )
    return Pipeline([("pre", pre), ("model", model)])


# -- training data -------------------------------------------------------------


@dataclass
class TrainingData:
    """Feature matrix, labels and per-row keys for every loaded feature row."""

    X: pd.DataFrame
    y: np.ndarray
    issue_start: date  # first issue day; issue_idx is days since it
    issue_idx: np.ndarray  # 0-based position in the contiguous issue range
    station_idx: np.ndarray  # index into stations
    hour_idx: np.ndarray  # target hour 0..23 within the issue day
    stations: list[str]
    district: np.ndarray  # per-row district string


def _pos(data: TrainingData, day: date) -> int:
    """Issue-day position: issue_days are contiguous, so the position is the
    day offset from the first issue."""
    return (day - data.issue_start).days


def build_training_data(
    features_table: pa.Table, demand: DemandTable, issue_days: list[date]
) -> TrainingData:
    """Assemble the training matrix: features from the contract read path,
    labels joined from realized demand at (station_id, hour_utc)."""
    t_us = np.array(
        [int(issue_time_utc(d).timestamp() * 1_000_000) for d in issue_days], dtype=np.int64
    )

    avail = features_table["available_at"].cast(pa.int64()).to_numpy()
    issue_idx = np.searchsorted(t_us, avail)
    if issue_idx.size and (
        int(issue_idx.max()) >= len(t_us)
        or not np.array_equal(t_us[np.minimum(issue_idx, len(t_us) - 1)], avail)
    ):
        raise ValueError("feature rows stamped outside the issue range cannot be placed on a day")

    station_ids = np.asarray(features_table["station_id"].to_pylist(), dtype=object)
    codes, uniques = pd.factorize(station_ids)
    station_pos = np.array([demand.stations.index(u) for u in uniques], dtype=np.int64)
    station_idx = station_pos[codes].astype(np.int64)

    hours = features_table["hour_utc"].cast(pa.int64()).to_numpy()
    y = np.full(len(hours), np.nan)
    for si, sid in enumerate(demand.stations):
        rows = np.flatnonzero(station_idx == si)
        if not rows.size:
            continue
        dh, dv = demand.hours[sid], demand.values[sid]
        idx = np.minimum(np.searchsorted(dh, hours[rows]), len(dh) - 1)
        y[rows] = np.where(dh[idx] == hours[rows], dv[idx], np.nan)

    X = features_table.select(FEATURE_COLUMNS).to_pandas()
    for col in BIN_FEATURES:
        X[col] = X[col].astype("int8")

    hour_idx = np.asarray(features_table["hour_of_day"].to_pylist(), dtype=np.int64)
    if hour_idx.size and (int(hour_idx.min()) < 0 or int(hour_idx.max()) >= TARGET_HOURS):
        raise ValueError("feature rows carry a target hour outside the 24-hour window")
    district = np.asarray([demand.district[s] for s in station_ids], dtype=object)
    return TrainingData(
        X=X,
        y=y,
        issue_start=issue_days[0],
        issue_idx=issue_idx.astype(np.int64),
        station_idx=station_idx,
        hour_idx=hour_idx,
        stations=list(demand.stations),
        district=district,
    )


# -- selection -------------------------------------------------------------


def grid_configs(grid: dict[str, list]) -> list[dict]:
    """The search budget as a deterministic list of parameter dicts."""
    keys = sorted(grid)
    return [dict(zip(keys, combo, strict=True)) for combo in product(*(grid[k] for k in keys))]


def select_config(
    data: TrainingData,
    grid: dict[str, list],
    *,
    max_iter: int,
    seed: int,
    train_mask: np.ndarray,
    val_mask: np.ndarray,
    lineage_tags: dict[str, str],
) -> tuple[dict, Pipeline, list[dict]]:
    """Fit every grid config on the internal train split, score it on the
    internal validation split, return (best params, fitted pipeline, rows).

    Ties keep the first config in grid order, so the choice is deterministic.
    Every grid run is tracked with the same lineage tag schema as the
    protocol run (acceptance: a run without them cannot be reproduced).
    """
    tr = train_mask & np.isfinite(data.y)
    va = val_mask & np.isfinite(data.y)
    if not tr.any() or not va.any():
        raise ValueError("selection split has no labeled rows on one side")

    best: tuple[dict, Pipeline] | None = None
    rows: list[dict] = []
    for i, config in enumerate(grid_configs(grid)):
        pipe = make_pipeline(config, max_iter=max_iter, seed=seed)
        pipe.fit(data.X.loc[tr], data.y[tr])
        pred = pipe.predict(data.X.loc[va])
        m = error_metrics(pred, data.y[va])
        if m["mae"] is None:
            raise ValueError(f"config {config} scored no rows on the validation split")
        rows.append(
            {
                "config": config,
                "val_metrics": m,
                "n_train_rows": int(tr.sum()),
                "n_val_rows": int(va.sum()),
            }
        )
        with mlflow.start_run(run_name=f"grid-{i:02d}"):
            mlflow.log_params(
                {
                    **config,
                    "max_iter": max_iter,
                    "seed": seed,
                    "sel_train_rows": int(tr.sum()),
                    "sel_val_rows": int(va.sum()),
                }
            )
            mlflow.log_metrics(
                {"val_mae": m["mae"], "val_rmse": m["rmse"], "val_smape": m["smape"]}
            )
            mlflow.set_tags({**lineage_tags, "run_kind": "grid"})
        if best is None or m["mae"] < best[0]["val_metrics"]["mae"]:
            best = (rows[-1], pipe)
    assert best is not None
    return best[0]["config"], best[1], rows


def feature_importance(
    pipe: Pipeline,
    data: TrainingData,
    rows: np.ndarray,
    *,
    repeats: int,
    seed: int,
    max_rows: int = IMPORTANCE_MAX_ROWS,
) -> list[dict]:
    """Permutation importance (MAE increase in kWh) on the internal validation
    split. The pipeline's input is the raw feature frame, so importance is
    already per input feature; sorted descending."""
    rng = np.random.default_rng(seed)
    if rows.size > max_rows:
        rows = np.sort(rng.choice(rows, max_rows, replace=False))
    imp = permutation_importance(
        pipe,
        data.X.iloc[rows],
        data.y[rows],
        n_repeats=repeats,
        random_state=seed,
        scoring="neg_mean_absolute_error",
        n_jobs=1,
    )
    out = [
        {"feature": col, "importance_mae_kwh": _round(float(imp.importances_mean[i]))}
        for i, col in enumerate(FEATURE_COLUMNS)
    ]
    return sorted(out, key=lambda item: (-item["importance_mae_kwh"], item["feature"]))


# -- fold protocol -------------------------------------------------------------


def run_fold_protocol(
    data: TrainingData,
    demand: DemandTable,
    folds,
    *,
    config: dict,
    max_iter: int,
    seed: int,
    median_window_days: int,
) -> tuple[dict, dict, dict]:
    """The M03 protocol with the model as a third contestant: per fold, fit on
    every issue up to the fold's last training issue and predict the fold's
    issues; seasonal-naive and station-median run on identical rows. Returns
    (fold rows, pooled arrays, segment inputs)."""
    n_st = len(data.stations)
    names = ("model", "seasonal_naive", "station_median")
    pooled = {name: {"pred": [], "label": []} for name in names}
    fold_rows = []
    for fold in folds:
        fit_mask = (data.issue_idx <= _pos(data, fold.train_last_issue)) & np.isfinite(data.y)
        pipe = make_pipeline(config, max_iter=max_iter, seed=seed)
        pipe.fit(data.X.loc[fit_mask], data.y[fit_mask])
        fitted_median = fit_station_median(demand, fold.train_last_issue, median_window_days)

        issues = (fold.issue_end - fold.issue_start).days + 1
        model_p, naive_p, med_p, label_p = [], [], [], []
        for offset in range(issues):
            day = fold.issue_start + timedelta(days=offset)
            naive_pred, label = seasonal_naive(demand, day)
            naive_p.append(naive_pred)
            label_p.append(label)
            med_p.append(station_median_predictions(demand, fitted_median, day))

            rows = np.flatnonzero(data.issue_idx == _pos(data, day))
            grid_pred = np.full((n_st, TARGET_HOURS), np.nan)
            if rows.size:
                grid_pred[data.station_idx[rows], data.hour_idx[rows]] = pipe.predict(
                    data.X.iloc[rows]
                )
            model_p.append(grid_pred)

        model_p, naive_p, med_p, label_p = (
            np.concatenate(model_p),
            np.concatenate(naive_p),
            np.concatenate(med_p),
            np.concatenate(label_p),
        )
        pooled["model"]["pred"].append(model_p)
        pooled["model"]["label"].append(label_p)
        pooled["seasonal_naive"]["pred"].append(naive_p)
        pooled["seasonal_naive"]["label"].append(label_p)
        pooled["station_median"]["pred"].append(med_p)
        pooled["station_median"]["label"].append(label_p)
        fold_rows.append(
            {
                "issue_start": fold.issue_start.isoformat(),
                "issue_end": fold.issue_end.isoformat(),
                "train_last_issue": fold.train_last_issue.isoformat(),
                "issues": issues,
                "rows": int(model_p.size),
                "mae_model": error_metrics(model_p, label_p)["mae"],
                "mae_seasonal_naive": error_metrics(naive_p, label_p)["mae"],
                "mae_station_median": error_metrics(med_p, label_p)["mae"],
            }
        )
    n_total = sum((f.issue_end - f.issue_start).days + 1 for f in folds)
    return fold_rows, pooled, {"n_issues_total": n_total}


# -- report -----------------------------------------------------------------


def render_markdown(report: dict) -> str:
    sel = report["selection"]
    lines = [
        "# Model report (M04)",
        "",
        f"- Source data release: `{report['source_release_id']}` "
        f"(manifest `{report['source_manifest_sha256'][:12]}…`), features "
        f"`{report['feature_release_id']}` (manifest "
        f"`{report['feature_manifest_sha256'][:12]}…`).",
        f"- Candidate: sklearn HistGradientBoostingRegressor, selected config "
        f"`{sel['selected_config']}` (max_iter {report['model']['max_iter']}, "
        f"seed {report['model']['seed']}, early stopping off).",
        f"- Selection split: issues ≤ {sel['split']['train_end']} for training, "
        f"{sel['split']['val_start']} … {sel['split']['val_end']} for validation; "
        f"{len(sel['results'])} grid configs evaluated.",
        f"- Fold plan: {len(report['fold_plan']['folds'])} monthly folds, embargo "
        f"{report['fold_plan']['embargo_days']} d, skipped months: "
        f"{', '.join(report['fold_plan']['skipped_months']) or 'none'}.",
        "",
        "## Headline (pooled over the M03 folds)",
        "",
        "| Model | MAE | RMSE | sMAPE | Rows |",
        "|---|---|---|---|---|",
    ]
    for name, label in (
        ("model", "Model (selected config)"),
        ("station_median", "Station median (M03)"),
        ("seasonal_naive", "Seasonal naive (M03)"),
    ):
        m = report["results"][name]["overall"]
        lines.append(
            f"| {label} | {m['mae']:.3f} | {m['rmse']:.3f} | {m['smape']:.3f} | {m['n']} |"
        )
    acc = report["acceptance"]
    lines += [
        "",
        f"Gate: seasonal-naive MAE {acc['gate_mae']:.3f} kWh — candidate "
        f"{'**beats**' if acc['beats_seasonal_naive'] else '**does not beat**'} the baseline; "
        f"station median MAE {acc['median_mae']:.3f} kWh — "
        f"{'beats' if acc['beats_station_median'] else 'does not beat'} the stronger baseline.",
        "",
        "## Paired comparisons (positive difference: model worse)",
        "",
        "| Comparison | Mean |err| difference (kWh) | Bootstrap 95% CI |",
        "|---|---|---|",
    ]
    for key in ("model_vs_station_median", "model_vs_seasonal_naive"):
        pc = report["paired_comparison"][key]
        lines.append(
            f"| {key.replace('_', ' ')} | {pc['mean_abs_error_diff']:.4f} "
            f"| [{pc['ci95'][0]:.4f}, {pc['ci95'][1]:.4f}] |"
        )
    lines += [
        "",
        "## Per-fold MAE (kWh)",
        "",
        "| Fold | Model | Seasonal naive | Station median |",
        "|---|---|---|---|",
    ]
    for row in report["fold_plan"]["folds"]:
        lines.append(
            f"| {row['issue_start']} → {row['issue_end']} | {row['mae_model']:.3f} "
            f"| {row['mae_seasonal_naive']:.3f} | {row['mae_station_median']:.3f} |"
        )
    lines += [
        "",
        "## District segments — model vs station median",
        "",
        "| District | Model MAE | Median MAE | Delta (model − median) |",
        "|---|---|---|---|",
    ]
    for name in sorted(report["results"]["model"]["by_district"]):
        m = report["results"]["model"]["by_district"][name]["mae"]
        b = report["results"]["station_median"]["by_district"][name]["mae"]
        if m is None or b is None:
            continue
        lines.append(f"| {name} | {m:.3f} | {b:.3f} | {m - b:+.3f} |")
    lines += [
        "",
        "## Station segments — model vs station median",
        "",
        "| Station | Model MAE | Median MAE | Delta |",
        "|---|---|---|---|",
    ]
    for name in report["results"]["model"]["by_station"]:
        m = report["results"]["model"]["by_station"][name]["mae"]
        b = report["results"]["station_median"]["by_station"][name]["mae"]
        if m is None or b is None:
            continue
        lines.append(f"| {name} | {m:.3f} | {b:.3f} | {m - b:+.3f} |")
    lines += [
        "",
        "## Selection grid (internal split, validation MAE)",
        "",
        "| Config | Val MAE | Val RMSE |",
        "|---|---|---|",
    ]
    for row in sel["results"]:
        c = ", ".join(f"{k}={v}" for k, v in sorted(row["config"].items()))
        lines.append(
            f"| {c} | {row['val_metrics']['mae']:.4f} | {row['val_metrics']['rmse']:.4f} |"
        )
    lines += [
        "",
        "## Feature importance (permutation, MAE increase in kWh)",
        "",
        "| Feature | Importance |",
        "|---|---|",
    ]
    for item in report["feature_importance"][:15]:
        lines.append(f"| {item['feature']} | {item['importance_mae_kwh']:.4f} |")
    res = report["residuals"]
    lines += [
        "",
        "## Residual summary (model − label over pooled fold rows)",
        "",
        f"Bias {res['bias_kwh']:+.4f} kWh, mean |residual| {res['mean_abs_kwh']:.4f} kWh, "
        f"p90 |residual| {res['p90_abs_kwh']:.4f} kWh, p99 |residual| "
        f"{res['p99_abs_kwh']:.4f} kWh.",
        "",
        "The numbers in this report are reproducible from the release IDs and the "
        "parameters above; the same inputs render these exact bytes.",
        "",
    ]
    return "\n".join(lines)


def run_model_training(
    release_dir: Path,
    cfg: dict,
    features_dir: Path,
    out_dir: Path,
    *,
    tracking_uri: str = DEFAULT_TRACKING_URI,
    grid: dict[str, list] | None = None,
    max_iter: int = MAX_ITER,
    seed: int = RANDOM_SEED,
    sel_train_end: date = SEL_TRAIN_END,
    sel_val_start: date = SEL_VAL_START,
    sel_val_end: date = SEL_VAL_END,
    embargo_days: int = EMBARGO_DAYS,
    median_window_days: int = MEDIAN_WINDOW_DAYS,
    importance_repeats: int = IMPORTANCE_REPEATS,
    importance_max_rows: int = IMPORTANCE_MAX_ROWS,
) -> dict:
    """Grid selection on the internal split, then the M03 fold protocol with
    both baselines; writes model-report.json/.md with deterministic bytes and
    tracks every run to MLflow with the lineage tag schema."""
    release_dir, features_dir, out_dir = Path(release_dir), Path(features_dir), Path(out_dir)
    grid = {k: list(v) for k, v in (grid or GRID).items()}

    demand = load_demand(release_dir, cfg)
    folds, skipped = build_folds(cfg, embargo_days=embargo_days)
    v_start, v_end = valid_issue_range(cfg)
    issue_days = [v_start + timedelta(days=i) for i in range((v_end - v_start).days + 1)]
    table = load_training_features(features_dir, v_start, v_end)
    data = build_training_data(table, demand, issue_days)

    manifest = json.loads((release_dir / "manifest.json").read_text(encoding="utf-8"))
    fmanifest = json.loads((features_dir / "manifest.json").read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    # M05 keys report reuse from the release checkout even when outputs live elsewhere.
    commit = git_commit(release_dir)
    lineage_tags = {
        "stage": "m04",
        "data_release_id": manifest["release_id"],
        "feature_release_id": fmanifest["feature_release_id"],
        "git_sha": commit,
        "fold_plan": json.dumps(
            {
                "embargo_days": embargo_days,
                "min_train_issues": MIN_TRAIN_ISSUES,
                "n_folds": len(folds),
                "skipped_months": skipped,
            },
            sort_keys=True,
        ),
    }

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(EXPERIMENT_NAME)

    sel_train = data.issue_idx <= _pos(data, sel_train_end)
    sel_val = (data.issue_idx >= _pos(data, sel_val_start)) & (
        data.issue_idx <= _pos(data, sel_val_end)
    )
    best_config, best_pipe, sel_rows = select_config(
        data,
        grid,
        max_iter=max_iter,
        seed=seed,
        train_mask=sel_train,
        val_mask=sel_val,
        lineage_tags=lineage_tags,
    )

    fold_rows, pooled, meta = run_fold_protocol(
        data,
        demand,
        folds,
        config=best_config,
        max_iter=max_iter,
        seed=seed,
        median_window_days=median_window_days,
    )

    results = {}
    pooled_pred, pooled_label, pooled_err = {}, {}, {}
    station_arr = np.array(data.stations)
    district_of_station = np.array([demand.district[s] for s in data.stations])
    district_names = sorted(set(demand.district.values()))
    for name in ("model", "seasonal_naive", "station_median"):
        pred = np.concatenate(pooled[name]["pred"]).ravel()
        label = np.concatenate(pooled[name]["label"]).ravel()
        pooled_pred[name], pooled_label[name] = pred, label
        pooled_err[name] = pred - label
        # Row order across the pooled arrays: fold → issue → station → hour.
        hour_seg = np.tile(np.arange(TARGET_HOURS), pred.size // TARGET_HOURS)
        st_seg = np.tile(np.repeat(station_arr, TARGET_HOURS), meta["n_issues_total"])
        dist_seg = np.tile(np.repeat(district_of_station, TARGET_HOURS), meta["n_issues_total"])
        results[name] = {
            "overall": error_metrics(pred, label),
            "by_hour": segment_metrics(pred, label, hour_seg, list(range(TARGET_HOURS))),
            "by_station": segment_metrics(pred, label, st_seg, data.stations),
            "by_district": segment_metrics(pred, label, dist_seg, district_names),
        }

    finite = np.isfinite(pooled_err["model"]) & np.isfinite(pooled_err["station_median"])
    resid = pooled_err["model"][finite]
    residuals = {
        "bias_kwh": _round(np.mean(resid)),
        "mean_abs_kwh": _round(np.mean(np.abs(resid))),
        "p90_abs_kwh": _round(np.percentile(np.abs(resid), 90)),
        "p99_abs_kwh": _round(np.percentile(np.abs(resid), 99)),
    }

    imp_rows = np.flatnonzero(sel_val & np.isfinite(data.y))
    importance = feature_importance(
        best_pipe,
        data,
        imp_rows,
        repeats=importance_repeats,
        seed=seed,
        max_rows=importance_max_rows,
    )

    model_mae = results["model"]["overall"]["mae"]
    naive_mae = results["seasonal_naive"]["overall"]["mae"]
    median_mae = results["station_median"]["overall"]["mae"]
    report = {
        "report_schema_version": MODEL_REPORT_SCHEMA_VERSION,
        "source_release_id": manifest["release_id"],
        "source_manifest_sha256": sha256_file(release_dir / "manifest.json"),
        "source_config_sha256": manifest["config_sha256"],
        "feature_release_id": fmanifest["feature_release_id"],
        "feature_manifest_sha256": sha256_file(features_dir / "manifest.json"),
        "source_commit": commit,
        "model": {
            "kind": "sklearn.HistGradientBoostingRegressor",
            "selected_config": best_config,
            "max_iter": max_iter,
            "seed": seed,
            "early_stopping": False,
            "threads_pinned": "OMP_NUM_THREADS=1",
        },
        "selection": {
            "split": {
                "train_end": sel_train_end.isoformat(),
                "val_start": sel_val_start.isoformat(),
                "val_end": sel_val_end.isoformat(),
                "train_rows": int(sel_train.sum()),
                "val_rows": int(sel_val.sum()),
            },
            "grid": grid,
            "results": sel_rows,
            "selected_config": best_config,
        },
        "fold_plan": {
            "embargo_days": embargo_days,
            "min_train_issues": MIN_TRAIN_ISSUES,
            "folds": fold_rows,
            "skipped_months": skipped,
        },
        "baseline_params": {"median_window_days": median_window_days},
        "results": results,
        "paired_comparison": {
            "model_vs_station_median": {
                "model_a": "model",
                "model_b": "station_median",
                **paired_bootstrap(pooled_err["model"], pooled_err["station_median"], seed=seed),
            },
            "model_vs_seasonal_naive": {
                "model_a": "model",
                "model_b": "seasonal_naive",
                **paired_bootstrap(pooled_err["model"], pooled_err["seasonal_naive"], seed=seed),
            },
        },
        "residuals": residuals,
        "feature_importance": importance,
        "acceptance": {
            "gate": "M03 protocol: pooled MAE over the monthly folds vs the "
            "seasonal-naive baseline",
            "beats_seasonal_naive": bool(model_mae < naive_mae),
            "beats_station_median": bool(model_mae < median_mae),
            "model_mae": model_mae,
            "gate_mae": naive_mae,
            "median_mae": median_mae,
        },
    }

    (out_dir / "model-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "model-report.md").write_text(render_markdown(report), encoding="utf-8")

    with mlflow.start_run(run_name="protocol"):
        mlflow.log_params(
            {
                **best_config,
                "max_iter": max_iter,
                "seed": seed,
                "embargo_days": embargo_days,
                "min_train_issues": MIN_TRAIN_ISSUES,
                "median_window_days": median_window_days,
                "n_folds": len(folds),
            }
        )
        metrics = {
            "mae_model": model_mae,
            "mae_seasonal_naive": naive_mae,
            "mae_station_median": median_mae,
        }
        metrics.update(
            {f"mae_fold_{row['issue_start'][:7]}": row["mae_model"] for row in fold_rows}
        )
        mlflow.log_metrics(metrics)
        mlflow.set_tags({**lineage_tags, "run_kind": "protocol"})
        mlflow.log_artifact(str(out_dir / "model-report.json"))
        mlflow.log_artifact(str(out_dir / "model-report.md"))
    return report
