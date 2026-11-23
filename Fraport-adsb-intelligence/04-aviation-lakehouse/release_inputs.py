"""Validate the accepted Geometry v2 label contract and release lineage."""

import hashlib
import json
import re
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


PAYLOADS = {"contract.yaml", "data/part-0001.parquet"}
EVENT_KEY = ("day_utc", "flight_key")
INPUT_SCHEMA = pa.schema([
    ("day_utc", pa.date32()), ("flight_key", pa.string()), ("icao24", pa.string()),
    ("callsign", pa.string()), ("lastseen_epoch_s", pa.int64()),
    ("touchdown_estimate_epoch_s", pa.int64()), ("surface_start_epoch_s", pa.int64()),
    ("taxi_end_epoch_s", pa.int64()), ("taxi_in_s", pa.int64()),
    ("surface_point_count", pa.int64()), ("taxi_path_m", pa.float64()),
    ("mean_surface_gap_s", pa.float64()), ("max_surface_gap_s", pa.float64()),
    ("end_distance_m", pa.float64()), ("status", pa.string()),
])
KNOWN_STATUSES = {"labeled", "no_surface", "no_airborne_approach", "surface_without_approach",
                  "censored_few_points"}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_release(directory: Path) -> tuple[dict, pa.Table]:
    manifest_path = directory / "manifest.json"
    manifest = read_json(manifest_path)
    release_id = manifest.get("release_id", "")
    if not re.fullmatch(r"geometry-v2-\d{4}-(0[1-9]|1[0-2])", release_id):
        raise ValueError("expected a monthly Geometry v2 release ID")
    if directory.name != release_id:
        raise ValueError("release directory and manifest ID differ")
    contract = (manifest.get("data_product"), manifest.get("contract_version"),
                manifest.get("release_schema_version"), manifest.get("schema_version"),
                manifest.get("label_version"), manifest.get("grain"))
    if contract != ("ground-ops", "2", "release-v1", "gold-ground-ops-v1",
                    "taxi-in-geometry-v2", list(EVENT_KEY)):
        raise ValueError("unsupported Geometry v2 release contract")
    files = manifest["files"]
    if set(files) != PAYLOADS:
        raise ValueError("unexpected Geometry v2 release payloads")
    for name, entry in files.items():
        if file_digest(directory / name) != entry["sha256"]:
            raise ValueError(f"release checksum mismatch: {name}")
    for name in ("validation.json", "approval.json", "_SUCCESS"):
        control = read_json(directory / name)
        if control.get("release_id") != release_id:
            raise ValueError(f"release ID mismatch: {name}")
        if name == "validation.json" and control.get("status") != "passed":
            raise ValueError("release gate did not pass")
        if name == "approval.json" and (not control.get("approver") or control.get("contract_version") != "2"):
            raise ValueError("release approval is missing or belongs to another contract")
    source = pq.read_table(directory / "data/part-0001.parquet")
    if source.schema != INPUT_SCHEMA or len(source) != files["data/part-0001.parquet"]["rows"] or not len(source):
        raise ValueError("release Parquet schema or row count does not match its contract")
    created_at = datetime.fromisoformat(manifest["created_at"])
    if created_at.tzinfo is None:
        raise ValueError("manifest creation timestamp must have a timezone")
    lineage = {"release_id": release_id, "manifest_sha256": file_digest(manifest_path),
               "label_version": manifest["label_version"],
               "release_created_at_utc": created_at.astimezone(UTC).isoformat()}
    for name, value in lineage.items():
        source = source.append_column(name, pa.array([value] * len(source), type=pa.string()))
    return lineage, source


def check_silver(source: pa.Table, release_id: str) -> Counter:
    month = date.fromisoformat(release_id.removeprefix("geometry-v2-") + "-01")
    seen = set()
    counts = Counter()
    for row in source.to_pylist():
        day, key = (row[field] for field in EVENT_KEY)
        expected_key = f"{row['icao24']}:{row['lastseen_epoch_s']}"
        if (day is None or (day.year, day.month) != (month.year, month.month)
                or not row["icao24"] or row["lastseen_epoch_s"] is None or key != expected_key):
            raise ValueError("invalid event identity or day outside the release month")
        event = (day, key)
        if event in seen:
            raise ValueError("duplicate (day_utc, flight_key) in release")
        seen.add(event)
        status = row["status"]
        duration = row["taxi_in_s"]
        if status not in KNOWN_STATUSES:
            raise ValueError(f"unknown Geometry v2 coverage status: {status}")
        if status == "labeled":
            touchdown = row["touchdown_estimate_epoch_s"]
            start, end = row["surface_start_epoch_s"], row["taxi_end_epoch_s"]
            if (None in (touchdown, start, end, duration) or not touchdown < start < end
                    or duration != end - start or not 1 <= duration <= 2700):
                raise ValueError("invalid Geometry v2 taxi-in label or chronology")
        elif duration is not None:
            raise ValueError("unlabeled arrival has a taxi-in target")
        counts[status] += 1
    if counts["labeled"] * 2 < len(source):
        raise ValueError("label coverage is below the release minimum")
    return counts
