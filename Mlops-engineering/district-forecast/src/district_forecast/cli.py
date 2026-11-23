"""The district-forecast CLI, mirroring the reference workload's shape."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .dataset import build_dataset, validate_dataset
from .features import build_features
from .pipeline import run_pipeline


def _config(args: argparse.Namespace) -> dict:
    from .dataset import load_config

    return load_config(Path(args.config))


def cmd_build_dataset(args: argparse.Namespace) -> None:
    cfg = _config(args)
    manifest = build_dataset(cfg, Path(args.source_release), Path(args.release))
    checks = validate_dataset(cfg, Path(args.release))
    print(
        f"dataset {manifest['release_id']}: {len(manifest['files'])} files, "
        f"{len(checks)} checks passed"
    )


def cmd_build_features(args: argparse.Namespace) -> None:
    cfg = _config(args)
    manifest = build_features(cfg, Path(args.dataset_release), Path(args.out))
    print(
        f"features {manifest['feature_release_id']}: {manifest['rows']} rows "
        f"over {manifest['issues']} issues -> {args.out}"
    )


def cmd_run_baselines(args: argparse.Namespace) -> None:
    from .baselines import run_baselines

    cfg = _config(args)
    report = run_baselines(cfg, Path(args.dataset_release), Path(args.out))
    for name in ("district_seasonal_naive", "district_median"):
        print(f"{name}: MAE {report['results'][name]['overall']['mae']}")


def cmd_run_pipeline(args: argparse.Namespace) -> None:
    cfg = _config(args)
    root = Path(args.workdir)
    paths = {
        "dataset": root / "data/releases/dataset-district",
        "features": root / "data/features",
        "baselines": root / "data/reports/baselines",
        "reports": root / "data/reports/protocol",
        "models": root / "data/models",
        "releases": root / "releases/models-district",
    }
    result = run_pipeline(cfg, Path(args.source_release), paths)
    mode = "reused" if result["reused"] else "published"
    print(
        f"model {result['release_id']} {mode}: MAE {result['manifest']['metrics']['mae']} "
        f"(baselines {result['manifest']['gate']['baselines']})"
    )
    if args.json:
        print(json.dumps({k: v for k, v in result.items() if k != "manifest"}, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="district-forecast", description=__doc__)
    parser.add_argument("--config", default="configs/district-v001.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build-dataset", help="derive the district dataset release")
    build.add_argument("--source-release", required=True)
    build.add_argument("--release", required=True)
    build.set_defaults(func=cmd_build_dataset)

    features = sub.add_parser("build-features", help="materialize the district feature release")
    features.add_argument("--dataset-release", required=True)
    features.add_argument("--out", required=True)
    features.set_defaults(func=cmd_build_features)

    baselines = sub.add_parser("run-baselines", help="run the fold plan and both baselines")
    baselines.add_argument("--dataset-release", required=True)
    baselines.add_argument("--out", required=True)
    baselines.set_defaults(func=cmd_run_baselines)

    pipeline = sub.add_parser(
        "run-pipeline", help="validate → dataset → features → train → publish"
    )
    pipeline.add_argument("--source-release", required=True)
    pipeline.add_argument("--workdir", default=".")
    pipeline.add_argument("--json", action="store_true")
    pipeline.set_defaults(func=cmd_run_pipeline)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
