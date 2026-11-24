"""Evaluate a trusted local candidate and its frozen baseline on a later month."""

import argparse
import hashlib
import json
import pickle
import re
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

from boosted_candidate import metrics, selected_features
from median_baseline import HERE, TAXI_IN_MAX_SECONDS, load_dataset, sha256


def first_of_release(manifest: dict) -> date:
    release_id = manifest["label_release"]["release_id"]
    if not re.fullmatch(r"geometry-v2-\d{4}-(0[1-9]|1[0-2])", release_id):
        raise ValueError("expected a monthly Geometry v2 label release")
    return date.fromisoformat(release_id.removeprefix("geometry-v2-") + "-01")


def validate_evaluation(training: dict, evaluation: dict, rows: list[dict]) -> None:
    earlier, later = first_of_release(training), first_of_release(evaluation)
    if later <= earlier:
        raise ValueError("evaluation month must be later than the training month")
    for key in ("training_features", "availability", "rules", "code_sha256"):
        if training[key] != evaluation[key]:
            raise ValueError(f"training and evaluation differ in {key}")
    end = (later + timedelta(days=32)).replace(day=1)
    start_at = int(datetime.combine(later, datetime.min.time(), tzinfo=UTC).timestamp())
    end_at = int(datetime.combine(end, datetime.min.time(), tzinfo=UTC).timestamp())
    for row in rows:
        trigger, prediction = row["trigger_event_at"], row["prediction_at"]
        if trigger is None or prediction is None or not start_at <= trigger < end_at or prediction < trigger:
            raise ValueError("evaluation row is outside its release month or precedes its trigger")
        label = row["taxi_in_s"]
        usable = row["match_status"] == "matched_labeled"
        if usable != (label is not None) or (usable and not 1 <= label <= TAXI_IN_MAX_SECONDS):
            raise ValueError("invalid evaluation label or outcome status")


def comparison(rows: list[dict], predictions: np.ndarray, baseline_seconds: float) -> dict:
    if predictions.shape != (len(rows),) or not np.isfinite(predictions).all():
        raise ValueError("expected a finite candidate prediction for every row")
    included = [i for i, row in enumerate(rows) if row["match_status"] == "matched_labeled"]
    if not included:
        raise ValueError("evaluation month has no usable labels")
    actual = np.array([rows[i]["taxi_in_s"] for i in included], dtype=np.float64)
    candidate = metrics(actual, predictions[included])
    baseline = metrics(actual, np.full(len(actual), baseline_seconds, dtype=np.float64))
    days = defaultdict(lambda: {"predictions": 0, "labeled": []})
    for i, row in enumerate(rows):
        day = datetime.fromtimestamp(row["prediction_at"], UTC).date().isoformat()
        days[day]["predictions"] += 1
        if row["match_status"] == "matched_labeled":
            days[day]["labeled"].append(i)
    daily = []
    for day, group in sorted(days.items()):
        subset = group["labeled"]
        truth = np.array([rows[i]["taxi_in_s"] for i in subset], dtype=np.float64)
        candidate_mae = float(np.mean(np.abs(predictions[subset] - truth))) if subset else None
        baseline_mae = float(np.mean(np.abs(baseline_seconds - truth))) if subset else None
        daily.append({"day_utc": day, "predictions": group["predictions"], "evaluated_labels": len(subset),
                      "candidate_mae_seconds": candidate_mae, "baseline_mae_seconds": baseline_mae})
    improvement = baseline["mae"] - candidate["mae"]
    return {"predictions": len(rows), "evaluated_labels": len(included), "label_coverage": len(included) / len(rows),
            "candidate_metrics_seconds": candidate, "baseline_metrics_seconds": baseline,
            "mae_improvement_seconds": improvement,
            "mae_improvement_fraction": improvement / baseline["mae"] if baseline["mae"] else None,
            "beats_baseline_on_mae": improvement > 0, "daily": daily}


def log_run(report: dict, output: Path, tracking_dir: Path) -> str:
    import mlflow

    tracking_dir.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(f"sqlite:///{tracking_dir / 'tracking.db'}")
    client = mlflow.MlflowClient()
    experiment = client.get_experiment_by_name("frankfurt-airport-taxi-in")
    experiment_id = (experiment.experiment_id if experiment else client.create_experiment(
        "frankfurt-airport-taxi-in", artifact_location=(tracking_dir / "artifacts").as_uri()))
    with mlflow.start_run(experiment_id=experiment_id, run_name=report["evaluation_id"]) as run:
        mlflow.log_params({key: report[key] for key in ("candidate_id", "baseline_id", "model_sha256",
                          "evaluation_dataset_id", "evaluation_manifest_sha256", "training_dataset_id")})
        mlflow.log_metrics({"candidate_mae": report["candidate_metrics_seconds"]["mae"],
                            "baseline_mae": report["baseline_metrics_seconds"]["mae"],
                            "mae_improvement_seconds": report["mae_improvement_seconds"],
                            "label_coverage": report["label_coverage"]})
        mlflow.log_artifact(str(output / "evaluation-report.json"))
        return run.info.run_id


def run_evaluation(args) -> tuple[dict, str]:
    if args.output.exists():
        raise ValueError("choose a new output directory")
    training_path = args.training_features / "manifest.json"
    training = json.loads(training_path.read_bytes())
    evaluation, eval_hash, rows = load_dataset(args.evaluation_features)
    validate_evaluation(training, evaluation, rows)
    features = selected_features(evaluation)
    report_path = args.candidate / "candidate-report.json"
    candidate = json.loads(report_path.read_bytes())
    baseline = json.loads(args.baseline_report.read_bytes())
    if (candidate["feature_dataset_id"] != training["feature_dataset_id"]
            or candidate["feature_manifest_sha256"] != sha256(training_path)
            or candidate["label_release_id"] != training["label_release"]["release_id"]
            or candidate["feature_columns"] != features
            or candidate["baseline_report_sha256"] != sha256(args.baseline_report)
            or candidate["baseline_id"] != baseline["baseline_id"]):
        raise ValueError("candidate, baseline or training manifest do not match the frozen evidence")
    constant = baseline["model"]["prediction_seconds"]
    if baseline["model"]["name"] != "historical_global_median" or not 1 <= constant <= TAXI_IN_MAX_SECONDS:
        raise ValueError("invalid frozen baseline model")
    model_path = args.candidate / "model.pkl"
    model_hash = sha256(model_path)
    if candidate["model_sha256"] != model_hash:
        raise ValueError("model checksum does not match the frozen candidate")
    # Only load an artifact from the trusted local training run.
    with model_path.open("rb") as stream:
        model = pickle.load(stream)
    if model["feature_columns"] != features:
        raise ValueError("frozen model feature order does not match the evaluation artifact")
    table = pq.read_table(args.evaluation_features / "training.parquet", columns=features)
    matrix = np.column_stack([table[name].to_numpy() for name in features]).astype(np.float64)
    if np.isinf(matrix).any():
        raise ValueError("evaluation feature contains infinite values")
    scores = comparison(rows, model["estimator"].predict(matrix), constant)
    inputs = {"candidate_id": candidate["candidate_id"], "candidate_report_sha256": sha256(report_path),
              "model_sha256": model_hash, "baseline_id": baseline["baseline_id"],
              "baseline_report_sha256": candidate["baseline_report_sha256"], "baseline_seconds": constant,
              "training_dataset_id": training["feature_dataset_id"],
              "training_manifest_sha256": candidate["feature_manifest_sha256"],
              "evaluation_dataset_id": evaluation["feature_dataset_id"], "evaluation_manifest_sha256": eval_hash,
              "evaluation_label_release_id": evaluation["label_release"]["release_id"],
              "availability": evaluation["availability"], "code_sha256": {name: sha256(HERE / name)
                  for name in ("frozen_evaluation.py", "boosted_candidate.py", "median_baseline.py", "uv.lock")}}
    identifier = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()[:16]
    report = {"evaluation_id": f"frozen-{identifier}", **inputs, **scores}
    args.output.mkdir(parents=True)
    (args.output / "evaluation-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    tracking_dir = (args.tracking_dir or args.output.parent / "mlflow").resolve()
    run_id = log_run(report, args.output, tracking_dir)
    (args.output / "run.json").write_text(json.dumps({"mlflow_run_id": run_id,
        "tracking_uri": f"sqlite:///{tracking_dir / 'tracking.db'}"}, indent=2) + "\n")
    return report, run_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-features", required=True, type=Path)
    parser.add_argument("--evaluation-features", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path, help="trusted local candidate directory")
    parser.add_argument("--baseline-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tracking-dir", type=Path)
    try:
        report, run_id = run_evaluation(parser.parse_args())
    except (KeyError, ValueError, OSError) as exc:
        parser.exit(1, f"evaluation: {exc}\n")
    print(json.dumps({key: report[key] for key in ("evaluation_id", "predictions", "evaluated_labels",
         "candidate_metrics_seconds", "baseline_metrics_seconds", "mae_improvement_seconds")}
         | {"mlflow_run_id": run_id}))


if __name__ == "__main__":
    main()
