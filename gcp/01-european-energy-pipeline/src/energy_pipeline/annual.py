"""Explicit, sequential annual preparation using the existing bounded client."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from energy_pipeline.audit import build_report, save_report, year_windows
from energy_pipeline.cli import revision, run
from energy_pipeline.download import Client
from energy_pipeline.normalize import ZONE, ValidationError


def prepare_year(year: int, cache: Path, output: Path) -> int:
    months = year_windows(year)
    if months[-1].end > datetime.now(UTC):
        raise ValidationError("prepare-year requires a fully completed calendar year")
    client = Client(cache)
    runs = output.resolve() / "runs"
    for index, window in enumerate(months, start=1):
        start = window.start.astimezone(ZONE).date().isoformat()
        until = window.end.astimezone(ZONE).date().isoformat()
        print(json.dumps({"month": f"{year}-{index:02d}", "status": "starting"}), flush=True)
        # One shared client/cache; denial/cooldown exceptions stop the loop.
        source = client.download(window)
        print(json.dumps({"month": f"{year}-{index:02d}", "cached": source.cached}), flush=True)
        args = argparse.Namespace(
            start=start,
            until=until,
            input=source.csv_path,
            source_manifest=source.manifest_path,
            timezone="Europe/Berlin",
            output=runs,
        )
        for repeat in range(2):
            if repeat:
                replay = client.download(window)
                if not replay.cached or replay.csv_path != source.csv_path:
                    raise ValidationError("expected cached replay; stopped for review")
                print(
                    json.dumps({"month": f"{year}-{index:02d}", "replay_cached": True}), flush=True
                )
            if run(args) != 0:
                print(json.dumps({"month": f"{year}-{index:02d}", "status": "validation_failed"}))
                return 1
    report = build_report(runs, year=year)
    report["audit_revision"] = revision()
    destination = save_report(report, output / "reports")
    print(json.dumps({"report_dir": str(destination), "status": report["status"]}), flush=True)
    return 0 if report["status"] == "passed" else 1
