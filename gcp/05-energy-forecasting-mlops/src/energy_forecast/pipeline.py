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
    PromotionRefused,
    promote_candidate,
    refuse_losing_candidate,
    register_baseline,
)
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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
