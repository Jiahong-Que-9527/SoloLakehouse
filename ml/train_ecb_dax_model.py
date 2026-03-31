"""Model training for ECB-to-DAX event impact classification."""

from __future__ import annotations

from typing import Any

import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import TimeSeriesSplit
from xgboost import XGBClassifier

FEATURE_COLUMNS = [
    "rate_change_bps",
    "rate_level_pct",
    "is_rate_hike",
    "is_rate_cut",
    "dax_volatility_pre_5d",
    "dax_pre_close",
]


def _make_model(model_type: str, params: dict[str, Any]) -> Any:
    if model_type == "xgboost":
        return XGBClassifier(
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=42,
            **params,
        )
    if model_type == "lightgbm":
        lightgbm_params = {"verbose": -1, **params}
        return LGBMClassifier(random_state=42, **lightgbm_params)
    raise ValueError(f"Unsupported model_type: {model_type}")


def train(
    df: pd.DataFrame, model_type: str = "xgboost", params: dict[str, Any] | None = None
) -> tuple[Any, dict[str, Any]]:
    """Train a binary classifier with TimeSeriesSplit cross-validation."""
    params = params or {}
    if len(df) < 6:
        raise ValueError("At least 6 rows are required for TimeSeriesSplit(n_splits=5)")

    training_df = df.copy()
    training_df = training_df.sort_values("event_date").reset_index(drop=True)

    x = training_df[FEATURE_COLUMNS].copy()
    x["is_rate_hike"] = x["is_rate_hike"].astype(int)
    x["is_rate_cut"] = x["is_rate_cut"].astype(int)
    y = (training_df["dax_return_1d"] > 0).astype(int)

    splitter = TimeSeriesSplit(n_splits=5)
    accuracy_scores: list[float] = []
    precision_scores: list[float] = []
    recall_scores: list[float] = []
    f1_scores: list[float] = []

    for train_idx, test_idx in splitter.split(x):
        fold_model = _make_model(model_type=model_type, params=params)
        fold_model.fit(x.iloc[train_idx], y.iloc[train_idx])
        predictions = fold_model.predict(x.iloc[test_idx])

        accuracy_scores.append(float(accuracy_score(y.iloc[test_idx], predictions)))
        precision_scores.append(
            float(precision_score(y.iloc[test_idx], predictions, zero_division=0))
        )
        recall_scores.append(float(recall_score(y.iloc[test_idx], predictions, zero_division=0)))
        f1_scores.append(float(f1_score(y.iloc[test_idx], predictions, zero_division=0)))

    model = _make_model(model_type=model_type, params=params)
    model.fit(x, y)

    metrics = {
        "accuracy": float(sum(accuracy_scores) / len(accuracy_scores)),
        "precision": float(sum(precision_scores) / len(precision_scores)),
        "recall": float(sum(recall_scores) / len(recall_scores)),
        "f1": float(sum(f1_scores) / len(f1_scores)),
        "n_splits": 5,
        "model_type": model_type,
        "params": params,
    }
    return model, metrics
