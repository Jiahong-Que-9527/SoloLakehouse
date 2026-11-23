"""Compare a local boosted taxi-in model with the pinned median baseline."""

import argparse
import hashlib
import json
import pickle
from datetime import UTC, date, datetime
from itertools import product
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from sklearn.ensemble import HistGradientBoostingRegressor

from median_baseline import HERE, TAXI_IN_MAX_SECONDS, evaluate, load_dataset, sha256

FEATURES = {
    "approach_speed_mps", "approach_altitude_m", "approach_vertical_rate_mps",
    "approach_distance_m", "ground_speed_mps", "approach_age_s", "prediction_hour_utc",
}
GRID = [{"max_leaf_nodes": leaves, "max_iter": iterations, "l2_regularization": penalty}
        for leaves, iterations, penalty in product((7, 15), (60, 120), (0.0, 1.0))]
MODEL_PARAMETERS = {"learning_rate": 0.05, "min_samples_leaf": 30, "early_stopping": False,
                    "loss": "absolute_error", "random_state": 42}


def selected_features(manifest: dict) -> list[str]:
    features = manifest["training_features"]
    if len(features) != len(FEATURES) or set(features) != FEATURES:
        raise ValueError("expected the seven approved project 04 feature columns")
    return features


def available_by(rows: list[dict], cutoff: int, window: int) -> list[int]:
    return [i for i, row in enumerate(rows)
            if row["match_status"] == "matched_labeled" and row["prediction_at"] < cutoff
            and row["trigger_event_at"] + window + TAXI_IN_MAX_SECONDS < cutoff]


def split_rows(rows: list[dict], validation_start: int, holdout_start: int, window: int) -> dict:
    if validation_start >= holdout_start:
        raise ValueError("validation must start before the holdout")
    outer_train = available_by(rows, holdout_start, window)
    split = {
        "tune_train": available_by(rows, validation_start, window),
        "validation": [i for i in outer_train if rows[i]["prediction_at"] >= validation_start],
        "train": outer_train,
        "holdout": [i for i, row in enumerate(rows) if row["match_status"] == "matched_labeled"
                    and row["prediction_at"] >= holdout_start],
    }
    if not all(split.values()):
        raise ValueError("each time split must have usable labels")
    return split


def metrics(actual, prediction) -> dict:
    errors = prediction - actual
    absolute = np.abs(errors)
    return {"mae": float(absolute.mean()), "rmse": float(np.sqrt(np.mean(errors ** 2))),
            "median_absolute_error": float(np.median(absolute)),
            "bias_prediction_minus_actual": float(errors.mean())}


def fit_candidate(matrix, targets, split: dict):
    tune_train, validation = split["tune_train"], split["validation"]
    trials = []
    for params in GRID:
        model = HistGradientBoostingRegressor(**MODEL_PARAMETERS, **params)
        model.fit(matrix[tune_train], targets[tune_train])
        mae = metrics(targets[validation], model.predict(matrix[validation]))["mae"]
        trials.append({"parameters": params, "validation_mae_seconds": mae})
    best = min(trials, key=lambda trial: trial["validation_mae_seconds"])
    model = HistGradientBoostingRegressor(**MODEL_PARAMETERS, **best["parameters"])
    model.fit(matrix[split["train"]], targets[split["train"]])
    return model, best, trials


def verify_baseline(baseline, manifest, manifest_hash, rows, cutoff, window) -> dict:
    if (baseline["feature_dataset_id"] != manifest["feature_dataset_id"]
            or baseline["feature_manifest_sha256"] != manifest_hash
            or baseline["label_release"] != manifest["label_release"]):
        raise ValueError("baseline is pinned to a different feature or label release")
    expected = evaluate(rows, cutoff, window)
    if any(baseline[key] != value for key, value in expected.items()):
        raise ValueError("baseline report does not reproduce on the pinned holdout")
    return expected


def log_run(report: dict, output: Path, tracking_dir: Path) -> str:
    import mlflow

    tracking_dir.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(f"sqlite:///{tracking_dir / 'tracking.db'}")
    client = mlflow.MlflowClient()
    experiment = client.get_experiment_by_name("fraport-taxi-in")
    experiment_id = (experiment.experiment_id if experiment else client.create_experiment(
        "fraport-taxi-in", artifact_location=(tracking_dir / "artifacts").as_uri()))
    with mlflow.start_run(experiment_id=experiment_id, run_name=report["candidate_id"]) as run:
        mlflow.log_params({"feature_dataset_id": report["feature_dataset_id"],
                           "feature_manifest_sha256": report["feature_manifest_sha256"],
                           "label_release_id": report["label_release_id"], "baseline_id": report["baseline_id"],
                           "holdout_from_utc": report["holdout_from_utc"],
                           "validation_from_utc": report["validation_from_utc"],
                           **report["model_parameters"]})
        mlflow.log_metrics({**report["holdout_metrics_seconds"],
                            "baseline_mae": report["baseline_holdout_metrics_seconds"]["mae"],
                            "mae_improvement_seconds": report["mae_improvement_seconds"],
                            "validation_mae": report["best_trial"]["validation_mae_seconds"]})
        mlflow.log_artifact(str(output / "candidate-report.json"))
        mlflow.log_artifact(str(output / "model.pkl"))
        return run.info.run_id


def run_candidate(features_dir: Path, baseline_path: Path, validation_from: date,
                  output: Path, tracking_dir: Path) -> tuple[dict, str]:
    if output.exists():
        raise ValueError("choose a new output directory")
    manifest, manifest_hash, rows = load_dataset(features_dir)
    features = selected_features(manifest)
    baseline = json.loads(baseline_path.read_bytes())
    holdout = datetime.fromisoformat(baseline["holdout_from_utc"])
    if holdout.utcoffset() != UTC.utcoffset(holdout) or holdout.time() != datetime.min.time():
        raise ValueError("expected a holdout at UTC midnight")
    validation = datetime.combine(validation_from, datetime.min.time(), tzinfo=UTC)
    window = manifest["rules"]["match_window_s"]
    cutoff = int(holdout.timestamp())
    expected = verify_baseline(baseline, manifest, manifest_hash, rows, cutoff, window)
    split = split_rows(rows, int(validation.timestamp()), cutoff, window)
    if len(split["train"]) != expected["train"]["used_labels"] or len(split["holdout"]) != expected["holdout"]["evaluated_labels"]:
        raise ValueError("candidate and baseline have different train or holdout populations")
    table = pq.read_table(features_dir / "training.parquet", columns=features)
    matrix = np.column_stack([table[name].to_numpy() for name in features]).astype(np.float64)
    if np.isinf(matrix).any():
        raise ValueError("prediction feature contains infinite values")
    targets = np.array([row["taxi_in_s"] for row in rows], dtype=np.float64)
    model, best, trials = fit_candidate(matrix, targets, split)
    heldout = split["holdout"]
    candidate_metrics = metrics(targets[heldout], model.predict(matrix[heldout]))
    baseline_metrics = expected["metrics_seconds"]
    improvement = baseline_metrics["mae"] - candidate_metrics["mae"]
    inputs = {"feature_dataset_id": manifest["feature_dataset_id"], "feature_manifest_sha256": manifest_hash,
              "label_release_id": manifest["label_release"]["release_id"], "availability": manifest["availability"],
              "baseline_id": baseline["baseline_id"], "baseline_report_sha256": sha256(baseline_path),
              "holdout_from_utc": holdout.isoformat(), "validation_from_utc": validation.isoformat(),
              "feature_columns": features, "model_parameters": {**MODEL_PARAMETERS, **best["parameters"]},
              "code_sha256": {name: sha256(HERE / name) for name in (
                  "boosted_candidate.py", "median_baseline.py", "uv.lock")}}
    key = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    output.mkdir(parents=True)
    model_path = output / "model.pkl"
    with model_path.open("wb") as stream:
        pickle.dump({"estimator": model, "feature_columns": features}, stream, protocol=5)
    report = {"candidate_id": f"boosted-{key[:16]}", **inputs,
              "split_labels": {name: len(indices) for name, indices in split.items()},
              "holdout_label_coverage": expected["holdout"]["label_coverage"],
              "best_trial": best, "trials": trials, "holdout_metrics_seconds": candidate_metrics,
              "baseline_holdout_metrics_seconds": baseline_metrics, "mae_improvement_seconds": improvement,
              "beats_baseline_on_mae": improvement > 0,
              "model_sha256": sha256(model_path)}
    (output / "candidate-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    tracking_dir = tracking_dir.resolve()
    run_id = log_run(report, output, tracking_dir)
    (output / "run.json").write_text(json.dumps({"mlflow_run_id": run_id,
        "tracking_uri": f"sqlite:///{tracking_dir / 'tracking.db'}"}, indent=2) + "\n")
    return report, run_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--baseline-report", type=Path, required=True)
    parser.add_argument("--validation-from", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tracking-dir", type=Path)
    args = parser.parse_args()
    try:
        report, run_id = run_candidate(args.features, args.baseline_report, args.validation_from, args.output,
                                       args.tracking_dir or args.output.parent / "mlflow")
    except (KeyError, ValueError, OSError) as exc:
        parser.exit(1, f"candidate: {exc}\n")
    print(json.dumps({"candidate_id": report["candidate_id"], "mlflow_run_id": run_id,
                      "metrics_seconds": report["holdout_metrics_seconds"],
                      "mae_improvement_seconds": report["mae_improvement_seconds"]}))


if __name__ == "__main__":
    main()
