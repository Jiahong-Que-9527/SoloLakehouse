"""Offline coverage and repeat-run checks against written Parquet artifacts."""

import hashlib
import json
import math
import re
import shutil
import tempfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq

from energy_pipeline.normalize import SCHEMA, STEP, ZONE, ValidationError, Window


def inspect_run(directory: Path) -> tuple[dict, list]:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    quality = json.loads((directory / "quality.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(quality, dict):
        raise ValidationError("manifest and quality report must be JSON objects")
    if not isinstance(manifest.get("run_id"), str) or not manifest["run_id"]:
        raise ValidationError("manifest must contain a nonempty run_id")
    start, end = (datetime.fromisoformat(manifest[key]) for key in ("window_start", "window_end"))
    if start.tzinfo is None or end.tzinfo is None:
        raise ValidationError("manifest window must contain timezone offsets")
    start, end = start.astimezone(UTC), end.astimezone(UTC)
    window = Window.from_dates(
        start.astimezone(ZONE).date().isoformat(), end.astimezone(ZONE).date().isoformat()
    )
    if (start, end) != (window.start, window.end):
        raise ValidationError("manifest window must use Europe/Berlin local midnights")
    parquet = directory / "observations.parquet"
    checksum = hashlib.sha256(parquet.read_bytes()).hexdigest()
    table = pq.read_table(parquet)
    if table.schema != SCHEMA:
        raise ValidationError("unexpected observation schema")
    rows = table.to_pylist()
    expected = [start + i * STEP for i in range(window.expected_rows)]
    starts = [r["interval_start"] for r in rows]
    expected_set = set(expected)
    actual_set = set(starts)
    keys = [(r["area"], r["metric"], r["interval_start"]) for r in rows]
    counts = {
        "expected_rows": window.expected_rows,
        "actual_rows": len(rows),
        "missing_intervals": len(expected_set - actual_set),
        "unexpected_intervals": len(actual_set - expected_set),
        "duplicate_keys": len(keys) - len(set(keys)),
        "invalid_durations": sum(
            r["interval_start"] is None
            or r["interval_end"] is None
            or r["interval_end"] - r["interval_start"] != STEP
            for r in rows
        ),
        "null_values": sum(r["value"] is None for r in rows),
        "nonfinite_values": sum(
            r["value"] is not None and not math.isfinite(r["value"]) for r in rows
        ),
        "invalid_dimensions": sum(
            (r["area"], r["metric"], r["unit"], r["source"])
            != ("DE", "actual_load_mwh", "MWh", "smard")
            for r in rows
        ),
    }
    expected_daily = Counter(t.astimezone(ZONE).date().isoformat() for t in expected)
    actual_daily = Counter(t.astimezone(ZONE).date().isoformat() for t in starts if t is not None)
    days = [
        {"date": day, "expected_rows": expected_daily[day], "actual_rows": actual_daily[day]}
        for day in sorted(expected_daily.keys() | actual_daily.keys())
    ]
    checks = {
        "source_checksum_recorded": bool(re.fullmatch(r"[0-9a-f]{64}", manifest["input_sha256"])),
        "parquet_checksum": checksum == manifest.get("output_sha256"),
        "row_counts": len(rows)
        == window.expected_rows
        == manifest.get("row_count")
        == quality.get("row_count")
        == quality.get("expected_rows"),
        "prior_quality": manifest.get("quality_status") == quality.get("status") == "passed"
        and quality.get("errors") == [],
        "complete_unique_grid": starts == expected,
        "valid_values_and_dimensions": all(
            counts[field] == 0
            for field in (
                "invalid_durations",
                "null_values",
                "nonfinite_values",
                "invalid_dimensions",
            )
        ),
        "daily_coverage": actual_daily == expected_daily,
    }
    record = {
        "run_id": manifest["run_id"],
        "run_dir": str(directory),
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "local_from": start.astimezone(ZONE).date().isoformat(),
        "local_until": end.astimezone(ZONE).date().isoformat(),
        "input_sha256": manifest["input_sha256"],
        "output_sha256": checksum,
        "retrieved_at": manifest.get("retrieved_at"),
        "git_sha": manifest.get("git_sha"),
        "git_dirty": manifest.get("git_dirty"),
        "package_version": manifest.get("package_version"),
        "checks": checks,
        "counts": counts,
        "daily_coverage": days,
        "status": "passed" if all(checks.values()) else "failed",
    }
    return record, rows


def build_report(root: Path) -> dict:
    if not root.is_dir():
        raise ValidationError("--runs-root must be a directory of completed run directories")
    directories = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))
    if not directories:
        raise ValidationError("no completed run directories found")
    runs, errors, groups = [], [], defaultdict(list)
    for directory in directories:
        try:
            record, rows = inspect_run(directory)
            runs.append(record)
            groups[(record["window_start"], record["window_end"])].append((record, rows))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append({"run_dir": str(directory), "error": str(exc)})
    windows = []
    for _, items in sorted(groups.items()):
        first, first_rows = items[0]
        distinct_runs = len({record["run_id"] for record, _ in items}) == len(items)
        repeat = (
            len(items) >= 2
            and distinct_runs
            and all(
                record["input_sha256"] == first["input_sha256"]
                and record["output_sha256"] == first["output_sha256"]
                and record["retrieved_at"] == first["retrieved_at"]
                and rows == first_rows
                for record, rows in items[1:]
            )
        )
        passed = repeat and all(record["status"] == "passed" for record, _ in items)
        windows.append(
            {
                "local_from": first["local_from"],
                "local_until": first["local_until"],
                "window_start": first["window_start"],
                "window_end": first["window_end"],
                "run_count": len(items),
                "repeat_equal": repeat,
                "expected_rows": first["counts"]["expected_rows"],
                "status": "passed" if passed else "failed",
            }
        )
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "audit_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "runs_root": str(root),
        "windows": windows,
        "runs": runs,
        "errors": errors,
        "status": "passed"
        if windows and not errors and all(w["status"] == "passed" for w in windows)
        else "failed",
        "attribution": "Bundesnetzagentur | SMARD.de",
        "source_url": "https://www.smard.de/home/downloadcenter/download-marktdaten",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "scope": (
            "Offline coverage and cached replay; not source reconciliation or uptime measurement."
        ),
    }


def markdown(report: dict) -> str:
    lines = [
        "# Coverage audit",
        "",
        f"Status: {report['status']}",
        f"Generated at: {report['generated_at']}",
        "",
        "| Local window (exclusive end) | Expected rows | Runs | Repeat equal | Status |",
        "|---|---:|---:|---|---|",
    ]
    for window in report["windows"]:
        lines.append(
            f"| {window['local_from']} to {window['local_until']} | {window['expected_rows']} "
            f"| {window['run_count']} | {window['repeat_equal']} | {window['status']} |"
        )
    lines.extend(
        [
            "",
            "See report.json for daily counts, individual checks, hashes and errors.",
            "",
            report["scope"],
            "",
            f"Source: [{report['attribution']}]({report['source_url']}), "
            f"[CC BY 4.0]({report['license_url']}).",
            "Changes: timestamps normalized to UTC; coverage and replay statistics computed.",
        ]
    )
    return "\n".join(lines) + "\n"


def save_report(report: dict, output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".pending-", dir=output))
    destination = output / ("audit-" + staging.name.removeprefix(".pending-"))
    try:
        (staging / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (staging / "report.md").write_text(markdown(report), encoding="utf-8")
        staging.rename(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return destination
