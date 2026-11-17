"""Command-line runner with isolated outputs and source attribution."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import pyarrow.parquet as pq

from energy_pipeline.normalize import ValidationError, Window, normalize

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def revision() -> dict:
    """Record provenance without requiring Git in installed/container builds."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        return {"git_sha": sha, "git_dirty": bool(dirty)}
    except (OSError, subprocess.CalledProcessError):
        return {"git_sha": None, "git_dirty": None}


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    window = Window.from_dates(args.start, args.until)
    raw = args.input.read_bytes()
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "processed_at": datetime.now(UTC).isoformat(),
        "input_file": args.input.name,
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "window_start": window.start.isoformat(),
        "window_end": window.end.isoformat(),
        "source_timezone": args.timezone,
        "interval_minutes": 15,
        "area": "DE",
        "metric": "actual_load_mwh",
        "unit": "MWh",
        "source": "smard",
        "attribution": "Bundesnetzagentur | SMARD.de",
        "source_url": "https://www.smard.de/home/downloadcenter/download-marktdaten",
        "license": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "changes": "Parsed German numbers; converted local intervals to UTC; retained MWh.",
        "package_version": version("energy-pipeline"),
        **revision(),
    }
    if getattr(args, "source_manifest", None):
        source = json.loads(args.source_manifest.read_text(encoding="utf-8"))
        for field in ("input_sha256", "window_start", "window_end"):
            if source.get(field) != manifest[field]:
                raise ValidationError(f"source manifest {field} does not match input/window")
        manifest["retrieved_at"] = source["retrieved_at"]
        manifest["download_endpoint"] = source["endpoint"]
    quality = {"expected_rows": window.expected_rows, "status": "passed", "errors": []}
    table = None
    try:
        table = normalize(raw, window)
    except ValidationError as exc:
        quality.update(status="failed", errors=[str(exc)])

    args.output.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".pending-", dir=args.output))
    destination = args.output / run_id
    try:
        if table is not None:
            parquet = staging / "observations.parquet"
            pq.write_table(table, parquet, compression="zstd")
            manifest.update(
                row_count=table.num_rows,
                output_file=parquet.name,
                output_sha256=hashlib.sha256(parquet.read_bytes()).hexdigest(),
            )
            quality["row_count"] = table.num_rows
        manifest["quality_status"] = quality["status"]
        write_json(staging / "quality.json", quality)
        write_json(staging / "manifest.json", manifest)
        staging.rename(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    print(json.dumps({"run_dir": str(destination), **quality}))
    if table is None:
        print(f"validation failed: {quality['errors'][0]}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="energy-pipeline")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("normalize", help="Validate a complete SMARD CSV window")
    command.add_argument("--input", type=Path, required=True)
    command.add_argument("--from", dest="start", required=True, help="Local date YYYY-MM-DD")
    command.add_argument("--until", required=True, help="Exclusive local date YYYY-MM-DD")
    command.add_argument("--timezone", choices=["Europe/Berlin"], default="Europe/Berlin")
    command.add_argument("--output", type=Path, required=True, help="Parent of per-run directories")
    command.add_argument("--source-manifest", type=Path, help="Matching download.json provenance")
    download = commands.add_parser("download", help="Fetch a bounded SMARD actual-load CSV window")
    download.add_argument("--from", dest="start", required=True, help="Local date YYYY-MM-DD")
    download.add_argument("--until", required=True, help="Exclusive local date YYYY-MM-DD")
    download.add_argument("--cache", type=Path, default=Path("downloads"))
    download.add_argument("--normalize-output", type=Path, help="Also run local normalization")
    audit = commands.add_parser("audit", help="Audit Parquet coverage and repeat runs offline")
    audit.add_argument("--runs-root", type=Path, required=True)
    audit.add_argument("--output", type=Path, required=True, help="Parent of per-audit directories")
    audit.add_argument(
        "--year", type=int, help="Require all 12 months and publish a local snapshot"
    )
    annual = commands.add_parser(
        "prepare-year", help="Sequential monthly downloads and yearly audit"
    )
    annual.add_argument("--year", type=int, required=True)
    annual.add_argument("--cache", type=Path, default=Path("downloads"))
    annual.add_argument(
        "--output", type=Path, required=True, help="Root for monthly runs and reports"
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare-year":
            from energy_pipeline.annual import prepare_year

            return prepare_year(args.year, args.cache, args.output)
        if args.command == "audit":
            from energy_pipeline.audit import build_report, save_report

            report = build_report(args.runs_root, year=args.year)
            report["audit_revision"] = revision()
            destination = save_report(report, args.output)
            print(json.dumps({"report_dir": str(destination), "status": report["status"]}))
            return 0 if report["status"] == "passed" else 1
        if args.command == "download":
            from energy_pipeline.download import Client

            result = Client(args.cache).download(Window.from_dates(args.start, args.until))
            print(
                json.dumps(
                    {
                        "input_file": str(result.csv_path),
                        "download_manifest": str(result.manifest_path),
                        "cached": result.cached,
                    }
                )
            )
            if args.normalize_output is None:
                return 0
            args.input, args.source_manifest = result.csv_path, result.manifest_path
            args.output, args.timezone = args.normalize_output, "Europe/Berlin"
        return run(args)
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
