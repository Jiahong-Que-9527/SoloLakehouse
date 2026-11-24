"""Batch report rendered from the batch manifest."""

from __future__ import annotations

from typing import Any

from .batch import Batch
from .config import Config, ConfigError
from .manifest import read_manifest
from .util import write_json_atomic


def write_report(cfg: Config, batch: Batch) -> dict[str, Any]:
    """Write `report.json` and `report.md` for a batch that has been validated."""
    manifest = _manifest(cfg, batch)
    directory = cfg.paths.data_root / "reports" / "batches" / batch.id
    write_json_atomic(directory / "report.json", manifest)
    (directory / "report.md").write_text(_markdown(manifest))
    return {"outcome": manifest["outcome"], "path": str(directory / "report.md")}


def _manifest(cfg: Config, batch: Batch) -> dict[str, Any]:
    path = cfg.paths.data_root / "metadata" / "manifests" / "batches" / f"{batch.id}.json"
    manifest = read_manifest(path)
    if manifest is None:
        raise ConfigError(f"batch {batch.id} has not been validated")
    return manifest


def _markdown(manifest: dict[str, Any]) -> str:
    lines = [
        f"# Batch {manifest['batch_id']}",
        "",
        f"Month `{manifest['month']}`. Outcome: **{manifest['outcome']}**.",
        "",
        f"- Expected hours: {manifest['expected_hours']}",
        f"- Complete: {manifest['complete']}",
        f"- Empty: {manifest['empty']}",
        f"- Source gap: {manifest['source_gap']}",
        f"- Failed or missing: {manifest['failed']}",
        f"- Rows: {manifest['rows']}",
        f"- Parquet bytes: {manifest['bytes']}",
        f"- Query seconds: {manifest['elapsed_seconds']}",
        f"- Flights complete: {manifest['flights_complete']} of {manifest['expected_flights']}",
        f"- Flight rows: {manifest['flight_rows']}",
        f"- Files rehashed: {manifest['rehashed']}",
        "",
        "| Date | Hours | Rows | Parquet bytes | Query seconds | Flights |",
        "|------|------:|-----:|--------------:|--------------:|--------:|",
    ]
    for day in manifest["days"]:
        flights = day["flight_rows"] if day["flight_rows"] is not None else ""
        lines.append(
            f"| {day['date']} | {day['hours_complete']}/{day['hours_expected']} "
            f"| {day['rows']} | {day['bytes']} | {day['elapsed_seconds']} | {flights} |"
        )
    lines.extend(["", "## Problems", ""])
    problems = manifest["problems"]
    if problems:
        lines.extend(f"- `{item}`" for item in problems)
    else:
        lines.append("None.")
    lines.extend(["", "## Anomalies", ""])
    anomalies = manifest["anomalies"]
    if anomalies:
        lines.extend(
            f"- {item['hour']}: {item['rows']} rows, median {item['median_rows']}"
            for item in anomalies
        )
    else:
        lines.append("None.")
    lines.append("")
    return "\n".join(lines)
