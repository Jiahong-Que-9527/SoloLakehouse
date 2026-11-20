"""Publish a validated SMARD window: land raw, gate on quality, merge idempotently.

The flow follows design.md section 5: resolve the window, land the raw object,
validate before any publish, merge the window on the business key, and record
one release row per attempt (failed attempts never change published rows).

Ports (RawStore, Warehouse) decouple this flow from Google clients so every
behaviour is testable with in-memory fakes; the real adapters live in
cloud_gcp.py and import their client libraries lazily.
"""

import hashlib
import json
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from importlib.resources import files

import pyarrow as pa

from energy_pipeline.normalize import ZONE, ValidationError, Window, normalize

SAMPLES = {
    ("2026-06-08", "2026-06-15"): "sample_week.csv",
    ("2026-10-25", "2026-10-26"): "sample_autumn_day.csv",
}
LOCAL_DATES = "dates are Europe/Berlin local midnights"


@dataclass(frozen=True)
class PublishResult:
    run_id: str
    release_id: str
    row_count: int
    input_sha256: str
    quality_status: str  # "passed" | "failed"


class RawStore:
    """Port: immutable object storage. Committed objects are never overwritten."""

    def put_object(self, bucket: str, prefix: str, name: str, payload: bytes) -> str:
        raise NotImplementedError


class Warehouse:
    """Port: idempotent merge on (area, metric, interval_start) plus release rows."""

    def merge_observations(
        self,
        project: str,
        dataset: str,
        table: str,
        rows: pa.Table,
        release_id: str,
        ingested_at: datetime,
    ) -> int:
        raise NotImplementedError

    def insert_release(self, project: str, dataset: str, record: dict) -> None:
        raise NotImplementedError


def local_date(window: Window, edge: str) -> str:
    value = window.start if edge == "start" else window.end
    return value.astimezone(ZONE).date().isoformat()


def sample_window_bytes(window: Window) -> tuple[bytes, str]:
    """Return the packaged sample CSV for a known window, or raise."""
    key = (local_date(window, "start"), local_date(window, "end"))
    name = SAMPLES.get(key)
    if name is None:
        raise ValidationError(f"no packaged sample for window {key[0]}..{key[1]} ({LOCAL_DATES})")
    return (files("energy_pipeline") / "data" / name).read_bytes(), name


def build_manifest(
    *,
    run_id: str,
    now: datetime,
    input_name: str,
    input_sha256: str,
    window: Window,
    source: str,
    revision: dict | None,
) -> dict:
    return {
        "schema_version": 1,
        "run_id": run_id,
        "processed_at": now.isoformat(),
        "input_file": input_name,
        "input_sha256": input_sha256,
        "window_start": window.start.isoformat(),
        "window_end": window.end.isoformat(),
        "interval_minutes": 15,
        "area": "DE",
        "metric": "actual_load_mwh",
        "unit": "MWh",
        "source": source,
        "attribution": "Bundesnetzagentur | SMARD.de",
        "source_url": "https://www.smard.de/home/downloadcenter/download-marktdaten",
        "license": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "changes": "Synthetic sample in SMARD export shape; parsed, converted to UTC; MWh kept.",
        "package_version": version("energy-pipeline"),
        **(revision or {}),
    }


def publish_window(
    store: RawStore,
    warehouse: Warehouse,
    *,
    csv_bytes: bytes,
    window: Window,
    bucket: str,
    project: str,
    dataset: str,
    input_name: str = "sample.csv",
    source: str = "sample",
    now: datetime | None = None,
    revision: dict | None = None,
    execution_id: str | None = None,
) -> PublishResult:
    """Land, validate, merge and record one publish attempt for one window."""
    now = now or datetime.now(UTC)
    run_id = now.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex
    release_id = uuid.uuid4().hex
    input_sha256 = hashlib.sha256(csv_bytes).hexdigest()
    prefix = f"raw/{source}/de_load/dt={local_date(window, 'start')}"

    # Ingest and land raw before any validation; the manifest is written once
    # complete, after validation, so both objects are immutable and truthful.
    store.put_object(bucket, prefix, f"{run_id}.csv", csv_bytes)
    table = None
    errors: list[str] = []
    try:
        table = normalize(csv_bytes, window)
    except ValidationError as exc:
        errors.append(str(exc))
    quality_status = "passed" if table is not None else "failed"

    manifest = build_manifest(
        run_id=run_id,
        now=now,
        input_name=input_name,
        input_sha256=input_sha256,
        window=window,
        source=source,
        revision=revision,
    )
    if table is not None:
        manifest["row_count"] = table.num_rows
    manifest["quality_status"] = quality_status
    manifest_payload = (json.dumps(manifest, ensure_ascii=False) + "\n").encode("utf-8")
    store.put_object(bucket, prefix, f"{run_id}.manifest.json", manifest_payload)

    release = {
        "release_id": release_id,
        "window_start": local_date(window, "start"),
        "window_end": local_date(window, "end"),
        "input_checksum": input_sha256,
        "row_count": table.num_rows if table is not None else 0,
        "git_sha": (revision or {}).get("git_sha"),
        "execution_id": execution_id,
        "quality_status": quality_status,
        "published_at": now.isoformat(),
    }
    warehouse.insert_release(project, dataset, release)

    if table is None:
        return PublishResult(run_id, release_id, 0, input_sha256, "failed")

    published = table.append_column(
        pa.field("release_id", pa.string()),
        pa.array([release_id] * table.num_rows, pa.string()),
    ).append_column(
        pa.field("ingested_at", pa.timestamp("us", tz="UTC")),
        pa.array([now] * table.num_rows, pa.timestamp("us", tz="UTC")),
    )
    warehouse.merge_observations(project, dataset, "metric_observation", published, release_id, now)
    return PublishResult(run_id, release_id, table.num_rows, input_sha256, "passed")


def run_publish_cloud(args) -> int:
    """CLI handler for publish-cloud: resolve the packaged sample, then publish."""
    from energy_pipeline.cli import revision as code_revision
    from energy_pipeline.cloud_gcp import GcpRawStore, GcpWarehouse

    window = Window.from_dates(args.start, args.until)
    csv_bytes, input_name = sample_window_bytes(window)
    result = publish_window(
        GcpRawStore(),
        GcpWarehouse(),
        csv_bytes=csv_bytes,
        window=window,
        bucket=args.bucket,
        project=args.project,
        dataset=args.dataset,
        input_name=input_name,
        now=datetime.now(UTC),
        revision=code_revision(),
        execution_id=os.environ.get("CLOUD_RUN_EXECUTION"),
    )
    summary = {
        "release_id": result.release_id,
        "run_id": result.run_id,
        "row_count": result.row_count,
        "quality_status": result.quality_status,
    }
    if args.output is not None:
        from energy_pipeline.cli import write_json

        args.output.mkdir(parents=True, exist_ok=True)
        write_json(args.output / "release.json", summary)
    print(json.dumps(summary))
    if result.quality_status != "passed":
        print("validation failed; published rows unchanged", file=sys.stderr)
        return 1
    return 0
