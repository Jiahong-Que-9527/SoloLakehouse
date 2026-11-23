"""Baseline, candidate and the frozen holdout comparison (step 3).

The seasonal-naive baseline predicts the value observed at the same
interval seven days earlier — the feature row's ``lag_7d_mw``, so both
models score identical timestamps under identical missing-data rules.
The candidate is one gradient-boosted model (LightGBM, CPU, fixed seed,
deterministic single-thread fit) on the training contract's features
(lag, hour, weekday).

Settings are confirmed on validation; the recorded comparison is then
run once on the untouched holdout. The report is deterministic: no
wall-clock values, canonical-JSON bytes, with a replay tolerance the
acceptance check re-verifies.
"""

import numpy as np

from energy_forecast.canonical import canonical_checksum
from energy_forecast.dataset import TrainingDataset
from energy_forecast.features import lag_names
from energy_forecast.splits import Windows

FEATURES = [*lag_names(), "hour", "weekday"]

CANDIDATE_CONFIG = {
    "objective": "regression",
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_data_in_leaf": 40,
    "num_boost_round": 300,
    "seed": 20261123,
    "deterministic": True,
    "force_row_wise": True,
    "num_threads": 1,
}

REPLAY_TOLERANCE_MW = 1e-6

# The step-4 drill candidate: deliberately underfit (one split, one round)
# so the promotion gate refuses it and the refusal path is exercised.
LOSING_CANDIDATE_CONFIG = {
    "objective": "regression",
    "num_leaves": 2,
    "num_boost_round": 1,
    "seed": 20261123,
    "deterministic": True,
    "force_row_wise": True,
    "num_threads": 1,
}


def _matrix(rows: list[dict]) -> np.ndarray:
    return np.array([[row[name] for name in FEATURES] for row in rows], dtype=float)


def _labels(rows: list[dict]) -> np.ndarray:
    return np.array([row["load_mw"] for row in rows], dtype=float)


def _metrics(pred: np.ndarray, label: np.ndarray) -> dict:
    err = pred - label
    return {
        "mae_mw": round(float(np.abs(err).mean()), 6),
        "rmse_mw": round(float(np.sqrt((err**2).mean())), 6),
        "n": int(pred.size),
    }


def seasonal_naive_predictions(rows: list[dict]) -> np.ndarray:
    """The value at the same interval seven days earlier — ``lag_7d_mw``."""
    return np.array([row["lag_7d_mw"] for row in rows], dtype=float)


def fit_candidate(train_rows: list[dict], config: dict | None = None):
    """One LightGBM regressor under the given config (recorded in the run)."""
    import lightgbm as lgb

    config = dict(config or CANDIDATE_CONFIG)
    num_boost_round = config.pop("num_boost_round")
    train_set = lgb.Dataset(_matrix(train_rows), label=_labels(train_rows))
    return lgb.train(config, train_set, num_boost_round=num_boost_round)


def candidate_predictions(model, rows: list[dict]) -> np.ndarray:
    return model.predict(_matrix(rows))


def _split_rows(feature_rows: list[dict], windows: Windows, which: str) -> list[dict]:
    return [row for row in feature_rows if windows.contains(which, row["interval_start"])]


def run_evaluation(
    dataset: TrainingDataset,
    windows: Windows,
    feature_rows: list[dict],
    *,
    git_sha: str,
    seed: int = CANDIDATE_CONFIG["seed"],
    library_versions: dict | None = None,
    candidate_config: dict | None = None,
) -> tuple[dict, object, dict]:
    """Confirm the candidate on validation, then run the frozen holdout
    comparison. Returns (report, fitted model, per-split predictions)."""
    splits = {
        name: _split_rows(feature_rows, windows, name)
        for name in ("train", "validation", "holdout")
    }
    if not splits["train"] or not splits["validation"] or not splits["holdout"]:
        raise ValueError("every split needs feature rows")

    config = candidate_config or CANDIDATE_CONFIG
    model = fit_candidate(splits["train"], config)
    predictions = {
        "validation": {
            "baseline": seasonal_naive_predictions(splits["validation"]),
            "candidate": candidate_predictions(model, splits["validation"]),
        },
        "holdout": {
            "baseline": seasonal_naive_predictions(splits["holdout"]),
            "candidate": candidate_predictions(model, splits["holdout"]),
        },
    }
    labels = {name: _labels(splits[name]) for name in ("validation", "holdout")}

    def window(which: str) -> dict:
        return {
            "start": getattr(windows, f"{which}_start").isoformat(),
            "end_exclusive": getattr(windows, f"{which}_end_exclusive").isoformat(),
        }

    report = {
        "report_schema_version": "g05-eval-report-v1",
        "release_id": dataset.metadata["release_id"],
        "input_sha256": dataset.metadata["input_sha256"],
        "git_sha": git_sha,
        "seed": seed,
        "candidate": {
            "library": "lightgbm",
            "library_version": (library_versions or {}).get("lightgbm"),
            "config": dict(config),
            "features": FEATURES,
        },
        "baseline": {
            "name": "seasonal_naive_7d",
            "definition": "load_mw at the same interval seven days earlier",
        },
        "windows": {name: window(name) for name in ("train", "validation", "holdout")},
        "replay_tolerance_mw": REPLAY_TOLERANCE_MW,
        "validation": {
            "baseline": _metrics(predictions["validation"]["baseline"], labels["validation"]),
            "candidate": _metrics(predictions["validation"]["candidate"], labels["validation"]),
        },
        "holdout": {
            "baseline": _metrics(predictions["holdout"]["baseline"], labels["holdout"]),
            "candidate": _metrics(predictions["holdout"]["candidate"], labels["holdout"]),
        },
        "missing_data_rule": "identical rows for both models; rows without a readable "
        "seven-day lag are excluded before the split and counted in the dataset metadata",
    }
    return report, model, predictions


def report_checksum(report: dict) -> str:
    """Stable bytes for the committed evaluation report."""
    return canonical_checksum(report)
