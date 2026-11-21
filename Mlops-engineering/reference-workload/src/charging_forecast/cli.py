"""CLI for the charging forecast reference workload (M01).

Subcommands:
  generate --config <yaml> --out <dir>   build the data partitions
  validate --config <yaml> --release <dir>   run the validation suite
  publish  --config <yaml> --release <dir> --approver <name> [--notes ...]
      validate, then write manifest.json, contract.yaml, validation.json,
      approval.json and a last-written _SUCCESS (the ADR-003 release shape).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import yaml

from . import __version__
from .contract import build_manifest, git_commit, load_config, render_contract
from .generator import ChargingGenerator
from .validation import validate_release


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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
