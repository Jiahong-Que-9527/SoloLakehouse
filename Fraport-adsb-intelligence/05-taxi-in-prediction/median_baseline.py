"""Evaluate a historical-median taxi-in baseline on a pinned feature release."""

import argparse
import hashlib
import json
import math
import statistics
from datetime import UTC, date, datetime
from pathlib import Path

import pyarrow.parquet as pq


TAXI_IN_MAX_SECONDS = 2700  # Project 02 Geometry v2 label contract.
INPUT_COLUMNS = ["prediction_id", "trigger_event_at", "prediction_at", "match_status", "taxi_in_s"]
HERE = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_dataset(directory: Path) -> tuple[dict, str, list[dict]]:
    manifest_path = directory / "manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest["label_release"]["label_version"] != "taxi-in-geometry-v2":
        raise ValueError("unsupported taxi-in label version")
    parquet = directory / "training.parquet"
    entry = manifest["files"][parquet.name]
    if sha256(parquet) != entry["sha256"]:
        raise ValueError("training Parquet checksum does not match the manifest")
    rows = pq.read_table(parquet, columns=INPUT_COLUMNS).to_pylist()
    if not rows or len(rows) != entry["rows"] or len(rows) != manifest["predictions"]:
        raise ValueError("training row count does not match the manifest")
    if len({row["prediction_id"] for row in rows}) != len(rows):
        raise ValueError("duplicate prediction ID in the training artifact")
    return manifest, hashlib.sha256(manifest_bytes).hexdigest(), rows


def evaluate(rows: list[dict], cutoff: int, label_match_window_s: int) -> dict:
    if type(label_match_window_s) is not int or label_match_window_s < 0:
        raise ValueError("expected a nonnegative label match window in seconds")
    train, holdout = [], []
    train_predictions = holdout_predictions = embargoed_train_labels = 0
    for row in rows:
        event, prediction = row["trigger_event_at"], row["prediction_at"]
        if event is None or prediction is None or event > prediction:
            raise ValueError("prediction precedes its trigger or has no timestamp")
        label = row["taxi_in_s"]
        usable = row["match_status"] == "matched_labeled"
        if usable != (label is not None) or (usable and not 1 <= label <= TAXI_IN_MAX_SECONDS):
            raise ValueError("invalid taxi-in target or label status")
        if prediction < cutoff:
            train_predictions += 1
            if usable:
                latest_taxi_end = event + label_match_window_s + TAXI_IN_MAX_SECONDS
                if latest_taxi_end < cutoff:
                    train.append(label)
                else:
                    embargoed_train_labels += 1
        else:
            holdout_predictions += 1
            if usable:
                holdout.append(label)
    if not train or not holdout:
        raise ValueError("the split must contain usable training and held-out labels")

    predicted = statistics.median(train)
    errors = [predicted - actual for actual in holdout]
    absolute = [abs(error) for error in errors]
    return {
        "model": {"name": "historical_global_median", "prediction_seconds": predicted},
        "train": {"predictions": train_predictions, "used_labels": len(train),
                  "embargoed_labels": embargoed_train_labels},
        "holdout": {"predictions": holdout_predictions, "evaluated_labels": len(holdout),
                    "label_coverage": len(holdout) / holdout_predictions},
        "metrics_seconds": {"mae": statistics.fmean(absolute),
                            "rmse": math.sqrt(statistics.fmean(error * error for error in errors)),
                            "median_absolute_error": statistics.median(absolute),
                            "bias_prediction_minus_actual": statistics.fmean(errors)},
    }


def log_run(report: dict, tracking_dir: Path) -> str:
    import mlflow

    tracking_dir.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(f"sqlite:///{tracking_dir / 'tracking.db'}")
    name = "fraport-taxi-in"
    client = mlflow.MlflowClient()
    experiment = client.get_experiment_by_name(name)
    experiment_id = (experiment.experiment_id if experiment else client.create_experiment(
        name, artifact_location=(tracking_dir / "artifacts").as_uri()))
    with mlflow.start_run(experiment_id=experiment_id, run_name=report["baseline_id"]) as run:
        mlflow.log_params({"feature_dataset_id": report["feature_dataset_id"],
                           "feature_manifest_sha256": report["feature_manifest_sha256"],
                           "label_release_id": report["label_release"]["release_id"],
                           "label_manifest_sha256": report["label_release"]["manifest_sha256"],
                           "holdout_from_utc": report["holdout_from_utc"],
                           "availability_mode": report["availability"]["mode"],
                           "model": report["model"]["name"]})
        mlflow.log_metrics({**report["metrics_seconds"],
                            "holdout_label_coverage": report["holdout"]["label_coverage"],
                            "train_labels": report["train"]["used_labels"],
                            "holdout_labels": report["holdout"]["evaluated_labels"]})
        mlflow.log_dict(report, "baseline-report.json")
        return run.info.run_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", required=True, type=Path, help="feature artifact directory")
    parser.add_argument("--holdout-from", required=True, type=date.fromisoformat, help="first UTC holdout date")
    parser.add_argument("--output", required=True, type=Path, help="new directory for the baseline evidence")
    parser.add_argument("--tracking-dir", type=Path, help="local MLflow SQLite and artifact directory")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("choose a new output directory")
    cutoff = datetime.combine(args.holdout_from, datetime.min.time(), tzinfo=UTC)
    try:
        manifest, manifest_hash, rows = load_dataset(args.features)
        window = manifest["rules"]["match_window_s"]
        report = evaluate(rows, int(cutoff.timestamp()), window)
        inputs = {"feature_dataset_id": manifest["feature_dataset_id"], "feature_manifest_sha256": manifest_hash,
                  "label_release": manifest["label_release"], "availability": manifest["availability"],
                  "holdout_from_utc": cutoff.isoformat(), "label_match_window_s": window,
                  "taxi_in_max_seconds": TAXI_IN_MAX_SECONDS,
                  "code_sha256": {name: sha256(HERE / name) for name in ("median_baseline.py", "uv.lock")}}
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"baseline: {exc}\n")
    key = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    report = {"baseline_id": f"median-{key[:16]}", **inputs, **report}
    tracking_dir = (args.tracking_dir or args.output.parent / "mlflow").resolve()
    run_id = log_run(report, tracking_dir)
    args.output.mkdir(parents=True)
    (args.output / "baseline-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (args.output / "run.json").write_text(json.dumps({"mlflow_run_id": run_id,
        "tracking_uri": f"sqlite:///{tracking_dir / 'tracking.db'}"}, indent=2) + "\n")
    print(json.dumps({"baseline_id": report["baseline_id"], "mlflow_run_id": run_id,
                      "metrics_seconds": report["metrics_seconds"]}))


if __name__ == "__main__":
    main()
