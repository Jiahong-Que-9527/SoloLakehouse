"""Schemas, availability table and release-manifest helpers (M01).

The availability table is the machine-readable form of
docs/feature-contract.md: what a model issued at T may read. When code and
that document disagree, the document is authoritative; this module freezes
its M01 resolution. Release manifests follow the ADR-003 pattern.
"""

from __future__ import annotations

import hashlib
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ISSUE_TIMEZONE = ZoneInfo("Europe/Berlin")
UTC = UTC

# Physical type names used in schemas and contract YAML.
TS = "timestamp[us, tz=UTC]"

# Machine-readable availability table (docs/feature-contract.md v1, M02).
# readable_at_issue=False families exist in the dataset but must never be
# readable by a model issued at T. readability_bound=True means the row's
# available_at stamp IS the readability bound the builder/loader enforces;
# published schedules (calendar, tariff, events) are readable ahead of their
# stamps and join by schedule semantics instead.
AVAILABILITY_TABLE: dict[str, dict] = {
    "calendar": {
        "readable_at_issue": True,
        "readability_bound": False,
        "rule": "Published calendar: the row for any date in the window is "
        "readable at any issue time; joined by the target hour's UTC date.",
    },
    "station_attributes": {
        "readable_at_issue": True,
        "readability_bound": True,
        "rule": "Static per dataset release; a station enters at its active_from.",
    },
    "demand_lags": {
        "readable_at_issue": True,
        "readability_bound": True,
        "rule": "Fixed clock windows anchored at T; the lagged hour must close "
        "before T minus the ingestion delay (available_at <= T).",
    },
    "weather_forecasts": {
        "readable_at_issue": True,
        "readability_bound": True,
        "rule": "Only forecasts with available_at <= T, joined by forecast "
        "reference time; realized weather is never a feature.",
    },
    "tariff_events": {
        "readable_at_issue": True,
        "readability_bound": False,
        "rule": "Published schedules, known ahead of the target day; joined by "
        "effectiveness/coverage, not by stamp.",
    },
    "weather_realized": {
        "readable_at_issue": False,
        "readability_bound": True,
        "rule": "Never readable at issue time; exists for backtesting and monitoring only.",
    },
    "same_day_demand": {
        "readable_at_issue": False,
        "readability_bound": True,
        "rule": "Demand of the target day is the prediction target and is never "
        "readable at issue time.",
    },
}

TABLE_SCHEMAS: dict[str, list[tuple[str, str]]] = {
    "stations": [
        ("station_id", "string"),
        ("district", "string"),
        ("poi_category", "string"),
        ("capacity_kw", "float64"),
        ("active_from", TS),
        ("available_at", TS),
    ],
    "tariffs": [
        ("station_id", "string"),
        ("effective_from", TS),
        ("price_per_kwh", "float64"),
        ("available_at", TS),
    ],
    "holidays": [
        ("date", "date32"),
        ("name", "string"),
        ("is_public_holiday", "bool"),
        ("is_school_break", "bool"),
        ("available_at", TS),
    ],
    "events": [
        ("event_id", "string"),
        ("district", "string"),
        ("start_utc", TS),
        ("end_utc", TS),
        ("boost", "float64"),
        ("available_at", TS),
    ],
    "weather_obs": [
        ("district", "string"),
        ("hour_utc", TS),
        ("temperature_c", "float64"),
        ("precipitation_mm", "float64"),
        ("available_at", TS),
    ],
    "weather_fcst": [
        ("district", "string"),
        ("issue_at", TS),
        ("reference_hour_utc", TS),
        ("temperature_c", "float64"),
        ("precipitation_mm", "float64"),
        ("available_at", TS),
    ],
    "demand": [
        ("station_id", "string"),
        ("hour_utc", TS),
        ("demand_kwh", "float64"),
        ("available_at", TS),
    ],
}

TABLE_GRAIN: dict[str, list[str]] = {
    "stations": ["station_id"],
    "tariffs": ["station_id", "effective_from"],
    "holidays": ["date"],
    "events": ["event_id"],
    "weather_obs": ["district", "hour_utc"],
    "weather_fcst": ["district", "issue_at", "reference_hour_utc"],
    "demand": ["station_id", "hour_utc"],
}


def load_config(path: Path) -> dict:
    """Load and sanity-check one release config."""
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(cfg, dict):
        raise ValueError(f"config must be a mapping: {path}")
    for key in ("release_id", "schema_version", "seed", "window", "stations", "tariff"):
        if key not in cfg:
            raise ValueError(f"config missing required key {key!r}")
    cfg["_config_path"] = str(path)
    return cfg


def issue_time_utc(day: date) -> datetime:
    """06:00 Europe/Berlin on `day`, converted to UTC (the M01 issue time T)."""
    local = datetime(day.year, day.month, day.day, 6, 0, tzinfo=ISSUE_TIMEZONE)
    return local.astimezone(UTC)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit(repo_hint: Path | None = None) -> str:
    """Best-effort HEAD commit; 'unknown' outside a repository."""
    cmd = ["git", "rev-parse", "HEAD"]
    try:
        out = subprocess.run(
            cmd, cwd=repo_hint, capture_output=True, text=True, check=True, timeout=10
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


def render_contract(cfg: dict) -> dict:
    """Render the release contract document (mirrors the ADR-003 gate shape)."""
    fields: dict[str, list[str]] = {
        name: [col for col, _ in schema] for name, schema in TABLE_SCHEMAS.items()
    }
    return {
        "data_product": "charging-network-demand",
        "version": cfg["release_id"],
        "contract": {
            "schema_version": cfg["schema_version"],
            "grain": TABLE_GRAIN,
            "required_columns": fields,
            "field_policy": {c: "keep" for cols in fields.values() for c in cols},
            "availability_table": AVAILABILITY_TABLE,
        },
        "quality_gates": {
            "demand_min_kwh": 0.0,
            "demand_max_fraction_of_capacity": 1.0,
            "temperature_c_min": -35.0,
            "temperature_c_max": 45.0,
            "precipitation_mm_min": 0.0,
            "price_per_kwh_min": 0.0,
            "duplicate_keys_max": 0,
        },
        "release": {"approval_required": True},
    }


def build_manifest(release_dir: Path, cfg: dict, commit: str) -> dict:
    """Walk data/ (sorted, stable) and describe every file for the manifest.

    Deliberately excludes wall-clock timestamps: two materializations from the
    same seed and config must produce identical manifests.
    """
    release_dir = Path(release_dir)
    files = []
    for path in sorted((release_dir / "data").rglob("*")):
        if not path.is_file():
            continue
        files.append(
            {
                "path": path.relative_to(release_dir).as_posix(),
                "rows": _parquet_rows(path),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return {
        "release_id": cfg["release_id"],
        "schema_version": cfg["schema_version"],
        "kind": "dataset",
        "seed": cfg["seed"],
        "config_sha256": hashlib.sha256(Path(cfg["_config_path"]).read_bytes()).hexdigest(),
        "source_commit": commit,
        "files": files,
    }


def _parquet_rows(path: Path) -> int:
    import pyarrow.parquet as pq

    return pq.read_metadata(path).num_rows
