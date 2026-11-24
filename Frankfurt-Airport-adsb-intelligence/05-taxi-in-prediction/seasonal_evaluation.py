"""Compare the pinned M4 candidate and median across four held-out months."""

import argparse
import hashlib
import json
import pickle
from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pyarrow.parquet as pq

from boosted_candidate import metrics
from frozen_evaluation import first_of_release, validate_evaluation
from median_baseline import HERE, TAXI_IN_MAX_SECONDS, load_dataset, sha256

WINDOWS = {"2024-12": "winter", "2025-04": "spring", "2025-07": "summer", "2025-10": "autumn"}
LOCAL_ZONE = ZoneInfo("Europe/Berlin")
TRAFFIC_WINDOW_SECONDS = 3600
TRAFFIC_BOUNDARIES = (10, 20, 30)
TRAFFIC_GROUPS = ("0–9", "10–19", "20–29", "30+", "insufficient history")


def traffic_groups(prediction_times: list[int], month_start: int) -> list[str]:
    available = sorted(prediction_times)
    groups = []
    for timestamp in prediction_times:
        start = timestamp - TRAFFIC_WINDOW_SECONDS
        if start < month_start:
            groups.append(TRAFFIC_GROUPS[-1])
            continue
        count = bisect_left(available, timestamp) - bisect_left(available, start)
        groups.append(TRAFFIC_GROUPS[bisect_right(TRAFFIC_BOUNDARIES, count)])
    return groups


def score(samples: list[tuple[float, int | None]], baseline: float) -> dict:
    labeled = [(prediction, actual) for prediction, actual in samples if actual is not None]
    result = {"predictions": len(samples), "evaluated_labels": len(labeled),
              "label_coverage": len(labeled) / len(samples) if samples else None,
              "candidate_metrics_seconds": None, "baseline_metrics_seconds": None,
              "mae_improvement_seconds": None, "mae_improvement_fraction": None}
    if labeled:
        predictions, truth = np.asarray(labeled, dtype=np.float64).T
        candidate = metrics(truth, predictions)
        reference = metrics(truth, np.full_like(truth, baseline))
        improvement = reference["mae"] - candidate["mae"]
        result.update(candidate_metrics_seconds=candidate, baseline_metrics_seconds=reference,
                      mae_improvement_seconds=improvement,
                      mae_improvement_fraction=improvement / reference["mae"] if reference["mae"] else None)
    return result


def validate_pins(release: dict, training: dict, training_hash: str, baseline: dict,
                  baseline_hash: str, model_hash: str) -> float:
    if (release["schema_version"] != "frankfurt-airport-model-release-v1" or release["stage"] != "candidate"
            or training_hash != release["training_manifest_sha256"]
            or training["feature_dataset_id"] != release["training_dataset_id"]
            or training["label_release"]["release_id"] != release["training_release_id"]
            or training["training_features"] != release["feature_columns"]
            or training["availability"] != release["availability"]
            or baseline_hash != release["baseline_report_sha256"]
            or baseline["baseline_id"] != release["baseline_id"]
            or model_hash != release["artifact"]["sha256"]):
        raise ValueError("training features, baseline or model do not match the M4 release manifest")
    if baseline["model"]["name"] != "historical_global_median":
        raise ValueError("expected the frozen global median baseline")
    constant = baseline["model"]["prediction_seconds"]
    if not 1 <= constant <= TAXI_IN_MAX_SECONDS:
        raise ValueError("frozen baseline prediction is outside the taxi-in label range")
    return constant


def evaluate(release_path: Path, model_path: Path, training_path: Path, baseline_path: Path,
             evaluation_paths: list[Path]) -> dict:
    release = json.loads(release_path.read_bytes())
    training, training_hash, _ = load_dataset(training_path)
    baseline = json.loads(baseline_path.read_bytes())
    constant = validate_pins(release, training, training_hash, baseline, sha256(baseline_path), sha256(model_path))
    features = release["feature_columns"]
    # Load only the trusted local model from the release whose checksum was verified above.
    with model_path.open("rb") as stream:
        model = pickle.load(stream)
    if model["feature_columns"] != features:
        raise ValueError("model feature order differs from the release manifest")

    months = {}
    for path in evaluation_paths:
        manifest, digest, rows = load_dataset(path)
        first = first_of_release(manifest)
        month = first.strftime("%Y-%m")
        if month not in WINDOWS or month in months:
            raise ValueError(f"unexpected or duplicate evaluation month: {month}")
        validate_evaluation(training, manifest, rows)
        months[month] = (path, first, manifest, digest, rows)
    if months.keys() != WINDOWS.keys():
        raise ValueError("expected December 2024 and April, July and October 2025")
    _, _, winter, winter_hash, _ = months["2024-12"]
    if winter["feature_dataset_id"] != release["evaluation_dataset_id"] or winter_hash != release["evaluation_manifest_sha256"]:
        raise ValueError("December features do not match the frozen M4 evaluation")

    seasons = {}
    datasets = {}
    hours = defaultdict(list)
    traffic = defaultdict(list)
    overall = []
    for month, season in WINDOWS.items():
        path, first, manifest, digest, rows = months[month]
        table = pq.read_table(path / "training.parquet", columns=features)
        matrix = np.column_stack([table[name].to_numpy() for name in features]).astype(np.float64)
        if np.isinf(matrix).any():
            raise ValueError(f"infinite feature value in {month}")
        predictions = model["estimator"].predict(matrix)
        if predictions.shape != (len(rows),) or not np.isfinite(predictions).all():
            raise ValueError(f"expected one finite prediction per row in {month}")
        timestamps = [row["prediction_at"] for row in rows]
        start = int(datetime.combine(first, datetime.min.time(), tzinfo=UTC).timestamp())
        start += manifest["availability"]["delay_seconds"] or 0
        groups = traffic_groups(timestamps, start)
        samples = []
        for timestamp, group, prediction, row in zip(timestamps, groups, predictions, rows, strict=True):
            sample = (float(prediction), row["taxi_in_s"])
            samples.append(sample)
            hours[datetime.fromtimestamp(timestamp, LOCAL_ZONE).hour].append(sample)
            traffic[group].append(sample)
        overall.extend(samples)
        seasons[season] = score(samples, constant)
        if not seasons[season]["evaluated_labels"]:
            raise ValueError(f"no usable evaluation labels for {month}")
        datasets[month] = {"season": season, "feature_dataset_id": manifest["feature_dataset_id"],
                           "feature_manifest_sha256": digest,
                           "label_release_id": manifest["label_release"]["release_id"],
                           "training_parquet_sha256": manifest["files"]["training.parquet"]["sha256"]}

    winter_scores = seasons["winter"]
    if (winter_scores["candidate_metrics_seconds"] != release["december_frozen_metrics_seconds"]
            or winter_scores["baseline_metrics_seconds"] != release["december_frozen_baseline_metrics_seconds"]):
        raise ValueError("December scores differ from the published M4 metrics")

    inputs = {"model_release_id": release["model_release_id"], "model_sha256": release["artifact"]["sha256"],
              "model_release_manifest_sha256": sha256(release_path), "registry_model_uri": release["registry"]["model_uri"],
              "training_manifest_sha256": training_hash, "baseline_id": baseline["baseline_id"],
              "baseline_report_sha256": release["baseline_report_sha256"], "baseline_prediction_seconds": constant,
              "datasets": datasets, "availability": release["availability"], "local_timezone": LOCAL_ZONE.key,
              "traffic_window_seconds": TRAFFIC_WINDOW_SECONDS, "traffic_boundaries": TRAFFIC_BOUNDARIES,
              "code_sha256": {name: sha256(HERE / name) for name in (
                  "seasonal_evaluation.py", "frozen_evaluation.py", "median_baseline.py", "boosted_candidate.py", "uv.lock")}}
    identifier = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()[:16]
    return {"evaluation_id": f"seasonal-{identifier}", **inputs, "overall": score(overall, constant),
            "by_season": seasons, "by_local_hour": {f"{hour:02d}": score(hours[hour], constant) for hour in range(24)},
            "by_traffic": {group: score(traffic[group], constant) for group in TRAFFIC_GROUPS}}


def markdown_row(label: str, group: dict) -> str:
    coverage = group["label_coverage"]
    coverage_text = f"{coverage:.1%}" if coverage is not None else "—"
    delta = group["mae_improvement_seconds"]
    errors = "— | — | —"
    if delta is not None:
        baseline = group["baseline_metrics_seconds"]["mae"]
        candidate = group["candidate_metrics_seconds"]["mae"]
        marker = " **worse**" if delta < 0 else ""
        errors = f"{baseline:.1f} | {candidate:.1f} | {delta:+.1f}{marker}"
    return f"| {label} | {group['predictions']:,} | {group['evaluated_labels']:,} | {coverage_text} | {errors} |"


def render_report(report: dict) -> str:
    header = ("| Group | Predictions | Usable labels | Coverage | Baseline MAE (s) | Candidate MAE (s) | Improvement (s) |",
              "|---|---:|---:|---:|---:|---:|---:|")
    lines = ["# EDDF taxi-in candidate evaluation", "", f"Evaluation `{report['evaluation_id']}` used model release",
             f"`{report['model_release_id']}` ({report['registry_model_uri']}) and the frozen",
             f"{report['baseline_prediction_seconds']}-second global median. Each season is represented by one",
             "held-out month. Overall MAE pools all usable labels. Coverage divides usable",
             "labels by all predictions. Positive improvement means lower candidate MAE.", "",
             f"The inputs use ADS-B proxy labels and a simulated {report['availability']['delay_seconds']}-second observation delay.",
             "Hourly groups use Europe/Berlin time, including daylight-saving changes. Traffic",
             "counts arrival triggers made available during the previous 60 minutes, including",
             "unlabeled arrivals and excluding the current second. The first incomplete hour",
             "of each month has its own group. Sparse groups have less evidence.", "",
             "## Overall and by season", "", *header, markdown_row("Overall", report["overall"])]
    for month, info in report["datasets"].items():
        season = info["season"]
        lines.append(markdown_row(f"{season.title()} · {month}", report["by_season"][season]))
    for title, key in (("By local hour", "by_local_hour"), ("By arrival triggers in the previous hour", "by_traffic")):
        lines.extend(["", f"## {title}", "", *header])
        lines.extend(markdown_row(label, group) for label, group in report[key].items())
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-manifest", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--training-features", required=True, type=Path)
    parser.add_argument("--baseline-report", required=True, type=Path)
    parser.add_argument("--evaluation-features", required=True, nargs=4, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = evaluate(args.release_manifest, args.model, args.training_features,
                          args.baseline_report, args.evaluation_features)
        markdown = render_report(report)
        args.output.mkdir(parents=True)
        (args.output / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        (args.output / "report.md").write_text(markdown)
    except (KeyError, ValueError, OSError) as exc:
        parser.exit(1, f"seasonal evaluation: {exc}\n")
    print(report["evaluation_id"])


if __name__ == "__main__":
    main()
