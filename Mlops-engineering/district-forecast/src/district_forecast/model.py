"""The district model and its fold protocol (M09 domain code).

One gradient-boosted regressor under the frozen M04 discipline:
`HistGradientBoostingRegressor` with the pinned hyperparameters, fit
bit-reproducibly with a single OpenMP thread and a fixed seed. The fold
protocol and metric comparison come from the template's `evaluation`
module.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")  # before sklearn loads (M04 discipline)

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from sklearn.ensemble import HistGradientBoostingRegressor

from .evaluation import build_folds, error_metrics
from .features import valid_issue_range

FEATURE_COLUMNS = [
    "days_since_start",
    "hour_of_day",
    "day_of_week",
    "is_public_holiday",
    "event_boost",
    "station_count",
    "capacity_kw_total",
    "tariff_price",
    "forecast_temperature_c",
    "forecast_precipitation_mm",
    "demand_lag_24h",
    "demand_lag_168h",
    "demand_rolling_7d",
]

MODEL_CONFIG = {
    "learning_rate": 0.1,
    "max_leaf_nodes": 63,
    "min_samples_leaf": 40,
    "max_iter": 300,
    "seed": 20261122,
}


def load_features(features_dir: Path) -> pa.Table:
    parts = sorted(Path(features_dir).rglob("issue_month=*/part-*.parquet"))
    if not parts:
        raise ValueError(f"no feature parts under {features_dir}")
    return pa.concat_tables([pq.read_table(p) for p in parts])


def design_matrix(table: pa.Table, districts: list[str]) -> np.ndarray:
    """Numeric features plus one-hot district columns, NaN rows kept for the
    evaluator to exclude on both sides of every comparison."""
    numeric = np.column_stack(
        [np.array(table[name].to_pylist(), dtype=float) for name in FEATURE_COLUMNS]
    )
    dist = np.asarray(table["district"].to_pylist())
    one_hot = np.column_stack([(dist == d).astype(float) for d in districts])
    return np.concatenate([numeric, one_hot], axis=1)


def fit_model(X: np.ndarray, y: np.ndarray) -> HistGradientBoostingRegressor:
    mask = np.isfinite(X).all(axis=1) & np.isfinite(y)
    model = HistGradientBoostingRegressor(
        learning_rate=MODEL_CONFIG["learning_rate"],
        max_leaf_nodes=MODEL_CONFIG["max_leaf_nodes"],
        min_samples_leaf=MODEL_CONFIG["min_samples_leaf"],
        max_iter=MODEL_CONFIG["max_iter"],
        early_stopping=False,
        random_state=MODEL_CONFIG["seed"],
    )
    model.fit(X[mask], y[mask])
    return model


def protocol_metrics(cfg: dict, features_dir: Path) -> dict:
    """Run the unchanged fold protocol: train per fold on issues up to the
    fold's train_last_issue, predict the fold's issue days, pool the errors."""
    table = load_features(features_dir)
    districts = list(cfg["districts"])
    X = design_matrix(table, districts)
    y = np.array(table["demand_kwh"].to_pylist(), dtype=float)
    issues = np.array([date.fromisoformat(d) for d in table["issue_date"].to_pylist()])
    first, last = valid_issue_range(cfg)
    folds, skipped = build_folds(cfg["window"])

    preds = np.full(len(y), np.nan)
    for fold in folds:
        train_mask = (issues <= fold.train_last_issue) & (issues >= first) & (issues <= last)
        model = fit_model(X[train_mask], y[train_mask])
        valid_mask = (issues >= fold.issue_start) & (issues <= fold.issue_end)
        fold_rows = np.flatnonzero(valid_mask)
        finite = np.isfinite(X[fold_rows]).all(axis=1) & np.isfinite(y[fold_rows])
        if not finite.all():
            raise ValueError("feature rows must be complete inside a fold's issue range")
        preds[fold_rows] = model.predict(X[fold_rows])

    pooled = error_metrics(preds, y)
    return {
        "pooled": pooled,
        "fold_plan": {
            "embargo_days": 1,
            "min_train_issues": 14,
            "n_folds": len(folds),
            "skipped_months": skipped,
        },
        "model_config": MODEL_CONFIG,
        "feature_columns": FEATURE_COLUMNS + [f"district_{d}" for d in districts],
        "preds": preds,
        "labels": y,
    }
