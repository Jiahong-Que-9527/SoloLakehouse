"""CLI for the charging forecast reference workload.

Subcommands:
  generate --config <yaml> --out <dir>   build the data partitions
  validate --config <yaml> --release <dir>   run the validation suite
  publish  --config <yaml> --release <dir> --approver <name> [--notes ...]
      validate, then write manifest.json, contract.yaml, validation.json,
      approval.json and a last-written _SUCCESS (the ADR-003 release shape).
  features-build --config <yaml> --release <dir> --issue-start <date>
      --issue-end <date> --out <dir>
      point-in-time features over the issue range, partitioned Parquet plus
      a feature manifest (M02).
  features-load --features <dir> --issue-date <date>
      the one read path: rows readable at the issue time T.
  features-check-leaks --features <dir> --issue-start <date> --issue-end <date>
      per-fold leakage check over the raw materialized rows (M02).
  eval-baselines --config <yaml> --release <dir> [--features <dir>] --out <dir>
      run the M03 protocol: monthly rolling-origin folds with embargo, both
      baselines, segment metrics and the seeded paired comparison; writes a
      deterministic baseline report (M03).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import yaml

from . import __version__
from . import eval as eval_mod
from .contract import build_manifest, git_commit, load_config, render_contract
from .features import (
    FeatureBuilder,
    check_fold_leakage,
    load_issue_features,
)
from .generator import ChargingGenerator
from .validation import validate_release


def _parse_date(text: str) -> date:
    return date.fromisoformat(text)


def _cmd_features_build(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    builder = FeatureBuilder(Path(args.release), cfg)
    manifest = builder.materialize(
        _parse_date(args.issue_start), _parse_date(args.issue_end), Path(args.out)
    )
    print(
        f"features {manifest['feature_release_id']}: {manifest['issues']} issues, "
        f"{manifest['rows']} rows, {len(manifest['files'])} partitions -> {args.out}"
    )
    return 0


def _cmd_features_load(args: argparse.Namespace) -> int:
    issue_day = _parse_date(args.issue_date)
    table = load_issue_features(Path(args.features), issue_day)
    print(f"readable at {issue_day} (T): {table.num_rows} rows")
    return 0


def _cmd_features_check_leaks(args: argparse.Namespace) -> int:
    failed = 0
    day = _parse_date(args.issue_start)
    end = _parse_date(args.issue_end)
    while day <= end:
        passed, detail = check_fold_leakage(Path(args.features), day)
        print(f"[{'PASS' if passed else 'FAIL'}] {detail}")
        failed += not passed
        day += timedelta(days=1)
    if failed:
        print(f"leakage check failed for {failed} fold(s)", file=sys.stderr)
        return 1
    print("no leakage detected across the fold range")
    return 0


def _cmd_generate(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    started = time.perf_counter()
    files = ChargingGenerator(cfg).generate(Path(args.out))
    elapsed = time.perf_counter() - started
    import pyarrow.parquet as pq

    rows = sum(pq.read_metadata(p).num_rows for p in files)
    size = sum(p.stat().st_size for p in files)
    print(
        f"release {cfg['release_id']}: {len(files)} files, {rows} rows, "
        f"{size / 1e6:.1f} MB, {elapsed:.2f}s -> {args.out}"
    )
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    results = validate_release(Path(args.release), cfg)
    failed = 0
    for check in results:
        mark = "PASS" if check.passed else "FAIL"
        print(f"[{mark}] {check.name}: {check.detail}")
        failed += not check.passed
    print(f"{len(results) - failed}/{len(results)} checks passed")
    return 1 if failed else 0


def _cmd_publish(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    release_dir = Path(args.release)
    results = validate_release(release_dir, cfg)
    failed = [c for c in results if not c.passed]
    if failed:
        for check in failed:
            print(f"[FAIL] {check.name}: {check.detail}", file=sys.stderr)
        print("release blocked: validation failed", file=sys.stderr)
        return 1

    commit = git_commit(release_dir)
    manifest = build_manifest(release_dir, cfg, commit)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    (release_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (release_dir / "contract.yaml").write_text(
        yaml.safe_dump(render_contract(cfg), sort_keys=False), encoding="utf-8"
    )
    (release_dir / "validation.json").write_text(
        json.dumps(
            {
                "release_id": cfg["release_id"],
                "config_sha256": manifest["config_sha256"],
                "source_commit": commit,
                "checked_at": now,
                "checks": [
                    {"name": c.name, "passed": c.passed, "detail": c.detail} for c in results
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (release_dir / "approval.json").write_text(
        json.dumps(
            {
                "release_id": cfg["release_id"],
                "approver": args.approver,
                "notes": args.notes,
                "approved_at": now,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    # _SUCCESS is written last, after every other file is in place (ADR-003).
    (release_dir / "_SUCCESS").write_text(
        json.dumps({"release_id": cfg["release_id"], "written_at": now}) + "\n",
        encoding="utf-8",
    )
    total_rows = sum(f["rows"] for f in manifest["files"])
    print(
        f"published {cfg['release_id']}: {len(manifest['files'])} files, "
        f"{total_rows} rows, commit {commit[:12]}"
    )
    return 0


def _cmd_eval_baselines(args: argparse.Namespace) -> int:
    report = eval_mod.run_baselines(
        Path(args.release),
        load_config(args.config),
        Path(args.out),
        embargo_days=args.embargo_days,
        median_window_days=args.median_window_days,
        seed=args.seed,
        features_dir=Path(args.features) if args.features else None,
    )
    folds = report["fold_plan"]["folds"]
    print(
        f"baseline report: {len(folds)} folds "
        f"(skipped: {', '.join(report['fold_plan']['skipped_months']) or 'none'}), "
        f"MAE seasonal-naive {report['results']['seasonal_naive']['overall']['mae']}, "
        f"MAE station-median {report['results']['station_median']['overall']['mae']} "
        f"-> {args.out}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="charging-forecast")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="build the data partitions")
    gen.add_argument("--config", required=True)
    gen.add_argument("--out", required=True)
    gen.set_defaults(func=_cmd_generate)

    val = sub.add_parser("validate", help="run the validation suite")
    val.add_argument("--config", required=True)
    val.add_argument("--release", required=True)
    val.set_defaults(func=_cmd_validate)

    pub = sub.add_parser("publish", help="gate and publish the release")
    pub.add_argument("--config", required=True)
    pub.add_argument("--release", required=True)
    pub.add_argument("--approver", required=True)
    pub.add_argument("--notes", default="")
    pub.set_defaults(func=_cmd_publish)

    fbuild = sub.add_parser("features-build", help="materialize point-in-time features")
    fbuild.add_argument("--config", required=True)
    fbuild.add_argument("--release", required=True)
    fbuild.add_argument("--issue-start", required=True)
    fbuild.add_argument("--issue-end", required=True)
    fbuild.add_argument("--out", required=True)
    fbuild.set_defaults(func=_cmd_features_build)

    fload = sub.add_parser("features-load", help="read features through the contract loader")
    fload.add_argument("--features", required=True)
    fload.add_argument("--issue-date", required=True)
    fload.set_defaults(func=_cmd_features_load)

    fleak = sub.add_parser("features-check-leaks", help="per-fold leakage check")
    fleak.add_argument("--features", required=True)
    fleak.add_argument("--issue-start", required=True)
    fleak.add_argument("--issue-end", required=True)
    fleak.set_defaults(func=_cmd_features_check_leaks)

    ev = sub.add_parser("eval-baselines", help="run the M03 baseline protocol")
    ev.add_argument("--config", required=True)
    ev.add_argument("--release", required=True)
    ev.add_argument("--features", default=None, help="optional features dir to record")
    ev.add_argument("--out", required=True)
    ev.add_argument("--embargo-days", type=int, default=eval_mod.EMBARGO_DAYS)
    ev.add_argument("--median-window-days", type=int, default=eval_mod.MEDIAN_WINDOW_DAYS)
    ev.add_argument("--seed", type=int, default=eval_mod.BOOTSTRAP_SEED)
    ev.set_defaults(func=_cmd_eval_baselines)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
