"""The repeatable G05 delivery drill (steps 3-4).

``promote`` runs the frozen comparison on the pinned fixture, registers
the baseline as version 1, gates the candidate and publishes the
evaluation report and model release manifest. ``refuse-drill`` runs the
deliberately losing candidate on its separate fixture and records the
gate refusal. Both commands are idempotent in their artifacts: the
report bytes are deterministic; registry versions accrue.
"""

import argparse
import json
import sys
from pathlib import Path

from energy_forecast.dataset import build_training_dataset
from energy_forecast.evaluation import LOSING_CANDIDATE_CONFIG, run_evaluation
from energy_forecast.features import build_features, count_excluded
from energy_forecast.fixture import LOSING_RELEASE_ID, losing_release, pinned_release
from energy_forecast.provenance import git_commit
from energy_forecast.registry import (
    REGISTRY_MODEL_NAME,
    PromotionRefused,
    promote_candidate,
    refuse_losing_candidate,
    register_baseline,
)
from energy_forecast.scoring import merge_statement, score_batch, verify_trace
from energy_forecast.splits import freeze_windows


def _prepare(rows, release):
    dataset = build_training_dataset(rows, release)
    windows, _spec = freeze_windows(dataset)
    features = build_features(dataset)
    return dataset, windows, features


def cmd_promote(args: argparse.Namespace) -> int:
    rows, release = pinned_release()
    dataset, windows, features = _prepare(rows, release)
    sha = git_commit()
    report, model, _preds = run_evaluation(dataset, windows, features, git_sha=sha)
    promotion = register_baseline(dataset, report, model, Path(args.tracking_dir), git_sha=sha)
    print(f"baseline registered as version {promotion.model_version}")
    try:
        candidate = promote_candidate(
            dataset, report, model, Path(args.tracking_dir), Path(args.releases_dir)
        )
    except PromotionRefused as exc:
        print(f"gate refused: {exc}")
        return 1
    print(f"candidate promoted as version {candidate.model_version} (run {candidate.run_id})")
    out = Path(args.releases_dir)
    (out / "evaluation-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest = json.loads((out / "model-manifest.json").read_text())
    print(
        f"manifest: gate {manifest['gate']['decision']}, "
        f"holdout MAE candidate {manifest['holdout_metrics']['candidate']['mae_mw']} MW "
        f"vs baseline {manifest['holdout_metrics']['baseline']['mae_mw']} MW"
    )
    print(f"features excluded before the seasonal lag: {count_excluded(dataset, features)}")
    return 0


def cmd_refuse(args: argparse.Namespace) -> int:
    rows, release = losing_release()
    dataset, windows, features = _prepare(rows, release)
    sha = git_commit()
    report, _model, _preds = run_evaluation(
        dataset, windows, features, git_sha=sha, candidate_config=LOSING_CANDIDATE_CONFIG
    )
    refusal = refuse_losing_candidate(release, report, Path(args.tracking_dir))
    print(
        f"gate refused release {LOSING_RELEASE_ID}: {refusal['reason']} "
        f"(experiment run {refusal['run_id']}, no registry version)"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="energy-forecast", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    promote = sub.add_parser("promote", help="evaluate, gate and register on the pinned fixture")
    promote.add_argument("--tracking-dir", default="data/mlflow")
    promote.add_argument("--releases-dir", default="releases")
    promote.set_defaults(func=cmd_promote)

    refuse = sub.add_parser("refuse-drill", help="run the deliberately losing candidate")
    refuse.add_argument("--tracking-dir", default="data/mlflow")
    refuse.set_defaults(func=cmd_refuse)

    score = sub.add_parser("score", help="score one holdout day into the BigQuery serving record")
    score.add_argument("--project", required=True)
    score.add_argument("--dataset", default="energy_ml")
    score.add_argument("--version", type=int, required=True)
    score.add_argument("--day", required=True, help="UTC day, e.g. 2026-06-29")
    score.add_argument("--tracking-dir", default="data/mlflow")
    score.add_argument("--releases-dir", default="releases")
    score.set_defaults(func=cmd_score)

    rollback = sub.add_parser("rollback", help="re-score the same window with the previous version")
    rollback.add_argument("--project", required=True)
    rollback.add_argument("--dataset", default="energy_ml")
    rollback.add_argument("--to-version", type=int, required=True)
    rollback.add_argument("--day", required=True)
    rollback.add_argument("--tracking-dir", default="data/mlflow")
    rollback.set_defaults(func=cmd_rollback)

    args = parser.parse_args(argv)
    return args.func(args)


# -- step 5: the BigQuery serving record ---------------------------------------

import subprocess  # noqa: E402
from datetime import UTC, datetime  # noqa: E402


def _bq(project: str, sql: str, job_id: str | None = None) -> str:
    cmd = ["bq", "query", "--use_legacy_sql=false", "--format=csv", f"--project_id={project}"]
    if job_id:
        cmd.append(f"--job_id={job_id}")
    cmd.append(sql)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        detail = (result.stderr + "\n" + result.stdout).strip()
        detail = "\n".join(
            line
            for line in detail.splitlines()
            if "urllib3" not in line
            and "warnings.warn" not in line
            and "RequestsDependency" not in line
        )
        raise RuntimeError(f"bq query failed: {detail[-400:]}")
    return result.stdout


def _ensure_dataset_and_table(project: str, dataset: str) -> str:
    """Idempotent bootstrap of the serving record (design §4, playbook §1);
    the dataset and table live outside Terraform and are recorded as-built."""
    exists = subprocess.run(
        ["bq", "show", f"--project_id={project}", f"{project}:{dataset}"],
        capture_output=True,
        text=True,
    )
    if exists.returncode != 0:
        subprocess.run(
            [
                "bq",
                "mk",
                "--dataset",
                "--location=europe-west3",
                f"--project_id={project}",
                dataset,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"created dataset {dataset} (europe-west3, outside Terraform; record as-built)")
    table = f"{project}:{dataset}.prediction"
    exists = subprocess.run(
        ["bq", "show", f"--project_id={project}", table], capture_output=True, text=True
    )
    if exists.returncode != 0:
        from energy_forecast.scoring import TABLE_DDL

        subprocess.run(
            ["bq", "mk", "--table", f"--project_id={project}", table, TABLE_DDL],
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"created table {dataset}.prediction")
    return table


def _load_model(version: int, tracking_dir: Path):
    import mlflow

    uri = f"sqlite:///{Path(tracking_dir) / 'mlflow.db'}"
    mlflow.set_tracking_uri(uri)
    mlflow.set_registry_uri(uri)
    return mlflow.lightgbm.load_model(f"models:/{REGISTRY_MODEL_NAME}/{version}")


def _score_window(version: int, day: str, tracking_dir: Path) -> tuple[list[dict], str, object]:
    from datetime import timedelta

    rows, release = pinned_release()
    dataset = build_training_dataset(rows, release)
    windows, _spec = freeze_windows(dataset)
    features = build_features(dataset)
    day_start = datetime.fromisoformat(f"{day}T00:00:00+00:00")
    window_rows = [
        row
        for row in features
        if day_start <= row["interval_start"] < day_start + timedelta(days=1)
    ]
    model = _load_model(version, tracking_dir)
    predicted_at = datetime.now(UTC)
    scored, batch_id = score_batch(
        model,
        window_rows,
        model_version=version,
        release_id=release.release_id,
        predicted_at=predicted_at,
    )
    return scored, batch_id, dataset


def cmd_score(args: argparse.Namespace) -> int:
    scored, batch_id, dataset = _score_window(args.version, args.day, Path(args.tracking_dir))
    _ensure_dataset_and_table(args.project, args.dataset)
    _bq(
        args.project,
        merge_statement(f"{args.project}.{args.dataset}.prediction", scored),
        job_id=f"g05_score_v{args.version}_{batch_id[-8:]}"[:128].replace("-", "_").lower(),
    )
    print(f"scored {len(scored)} intervals with version {args.version}; batch {batch_id}")
    manifest = json.loads((Path(args.releases_dir) / "model-manifest.json").read_text())
    traced = verify_trace(
        scored[0],
        manifest=manifest,
        feature_rows=build_features(dataset),
        expected_model=None,
    )
    print(f"trace: {traced}")
    return 0


def cmd_rollback(args: argparse.Namespace) -> int:
    table = f"{args.project}.{args.dataset}.prediction"
    previous = args.to_version
    scored, batch_id, _dataset = _score_window(previous, args.day, Path(args.tracking_dir))
    _bq(
        args.project,
        merge_statement(table, scored),
        job_id=f"g05_rollback_v{previous}_{batch_id[-8:]}"[:128].replace("-", "_").lower(),
    )
    print(f"rollback batch: version {previous}, {len(scored)} intervals, batch {batch_id}")
    counts = _bq(
        args.project,
        f"SELECT model_version, COUNT(*) AS n, MIN(batch_id) AS sample_batch "
        f"FROM `{table}` WHERE DATE(interval_start) = '{args.day}' "
        f"GROUP BY model_version ORDER BY model_version",
    )
    print("serving record by version:")
    print(counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
