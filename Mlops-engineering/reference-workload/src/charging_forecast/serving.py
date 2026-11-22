"""M06 · Batch scoring and shadow comparison of the pinned release.

The pin is the contract: every scored row carries the pinned manifest's
lineage, nothing loads an artifact that does not match its manifest
checksum, and a rerun over an already-scored issue time replaces nothing
silently — identical content is a no-op, different content under the same
release ID is a collision.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from charging_forecast.contract import issue_time_utc, sha256_file
from charging_forecast.eval import load_demand
from charging_forecast.features import load_training_features
from charging_forecast.pipeline import (
    ARTIFACT_NAME,
    DEFAULT_MODELS_DIR,
    DEFAULT_RELEASES_DIR,
    read_pin,
)
from charging_forecast.training import TARGET_HOURS, _round, build_training_data

SCORES_SCHEMA_VERSION = "charging-scores-v1"
SHADOW_SCHEMA_VERSION = "charging-shadow-v1"
DEFAULT_SCORES_DIR = Path("data/scores")
DEFAULT_SCORE_RELEASES_DIR = Path("releases/scores")
PREDICTIONS_NAME = "predictions.parquet"
TS_TYPE = pa.timestamp("us", tz="UTC")

_SCORES_SCHEMA = pa.schema(
    [
        ("model_release_id", pa.string()),
        ("mlflow_model_version", pa.int64()),
        ("data_release_id", pa.string()),
        ("feature_release_id", pa.string()),
        ("git_sha", pa.string()),
        ("issue_date", pa.string()),
        ("target_time", TS_TYPE),
        ("station_id", pa.string()),
        ("predicted_kwh", pa.float64()),
    ]
)


# -- pinned release ---------------------------------------------------------------


@dataclass
class Release:
    """A published release: manifest, verified artifact, loaded pipeline."""

    model_release_id: str
    manifest: dict
    manifest_sha256: str
    artifact_path: Path
    pipeline: Any


def load_release(
    model_release_id: str,
    *,
    releases_dir: Path = DEFAULT_RELEASES_DIR,
    models_dir: Path = DEFAULT_MODELS_DIR,
) -> Release:
    """Load a published release, verifying the artifact against its manifest."""
    releases_dir, models_dir = Path(releases_dir), Path(models_dir)
    manifest_path = releases_dir / model_release_id / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"no release manifest for {model_release_id}: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact_path = models_dir / model_release_id / ARTIFACT_NAME
    if sha256_file(artifact_path) != manifest["artifact"]["sha256"]:
        raise RuntimeError(f"artifact for {model_release_id} does not match its manifest checksum")
    return Release(
        model_release_id=model_release_id,
        manifest=manifest,
        manifest_sha256=sha256_file(manifest_path),
        artifact_path=artifact_path,
        pipeline=joblib.load(artifact_path),
    )


def load_pinned_release(
    *,
    releases_dir: Path = DEFAULT_RELEASES_DIR,
    models_dir: Path = DEFAULT_MODELS_DIR,
) -> Release:
    """Load the pinned release; refuse anything unpinned or tampered."""
    pin = read_pin(releases_dir)
    if pin is None:
        raise RuntimeError("no pinned release: write releases/models/pinned.json first")
    release = load_release(
        pin["model_release_id"], releases_dir=releases_dir, models_dir=models_dir
    )
    if release.manifest_sha256 != pin["manifest_sha256"]:
        raise RuntimeError("pinned manifest changed since the pin was written")
    return release


# -- batch scoring -----------------------------------------------------------------


def _feature_release_guard(pinned: Release, features_dir: Path) -> str:
    """The features must carry the same feature-contract major as the pinned
    manifest records; the exact manifest bytes stay lineage."""
    fmanifest = json.loads((Path(features_dir) / "manifest.json").read_text(encoding="utf-8"))
    feature_release_id = fmanifest.get("feature_release_id", "")
    major = "-".join(pinned.manifest["feature_release_id"].split("-")[:2])
    if not feature_release_id.startswith(f"{major}-"):
        raise RuntimeError(
            f"feature release {feature_release_id} does not match the pinned "
            f"feature contract {major} (pinned: {pinned.manifest['feature_release_id']})"
        )
    return feature_release_id


def _predict_day(pinned: Release, release_dir: Path, cfg: dict, features_dir: Path, day: date):
    """Score one issue day in memory; returns (stations, target_us, preds,
    training data with the aligned labels) sorted by (station, target hour)."""
    table = load_training_features(features_dir, day, day)
    demand = load_demand(release_dir, cfg)
    data = build_training_data(table, demand, [day])
    preds = pinned.pipeline.predict(data.X)
    stations = np.asarray(table["station_id"].to_pylist(), dtype=object)
    target_us = table["hour_utc"].cast(pa.int64()).to_numpy()
    order = np.lexsort((target_us, stations))
    return stations[order], target_us[order], preds[order], data


def _iso_us(us: int) -> str:
    return datetime.fromtimestamp(us / 1_000_000, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def score_issue_day(
    pinned: Release,
    release_dir: Path,
    cfg: dict,
    features_dir: Path,
    issue_date: str | date,
    *,
    scores_dir: Path = DEFAULT_SCORES_DIR,
    score_releases_dir: Path = DEFAULT_SCORE_RELEASES_DIR,
) -> dict:
    """Score one issue day with the pinned artifact and publish the score
    release: predictions Parquet under `scores_dir` (outside Git), the score
    manifest under `score_releases_dir` (committed). Idempotent per
    (model_release_id, issue_date): identical content is a no-op, different
    content is a collision. Returns the score manifest and whether the
    existing release was reused."""
    day = date.fromisoformat(issue_date) if isinstance(issue_date, str) else issue_date
    feature_release_id = _feature_release_guard(pinned, features_dir)

    stations, target_us, preds, _ = _predict_day(pinned, release_dir, cfg, features_dir, day)
    issue_us = int(issue_time_utc(day).timestamp() * 1_000_000)

    out_dir = Path(scores_dir) / pinned.model_release_id / day.isoformat()
    manifest_path = (
        Path(score_releases_dir) / pinned.model_release_id / day.isoformat() / "manifest.json"
    )
    parquet_path = out_dir / PREDICTIONS_NAME

    table = pa.table(
        {
            "model_release_id": pa.array([pinned.model_release_id] * len(preds)),
            "mlflow_model_version": pa.array(
                [pinned.manifest["mlflow_model_version"]] * len(preds), type=pa.int64()
            ),
            "data_release_id": pa.array([pinned.manifest["data_release_id"]] * len(preds)),
            "feature_release_id": pa.array([feature_release_id] * len(preds)),
            "git_sha": pa.array([pinned.manifest["source_commit"]] * len(preds)),
            "issue_date": pa.array([day.isoformat()] * len(preds)),
            "target_time": pa.array(target_us, type=TS_TYPE),
            "station_id": pa.array(stations.tolist()),
            "predicted_kwh": pa.array([_round(p) for p in preds], type=pa.float64()),
        },
        schema=_SCORES_SCHEMA,
    )

    tmp_dir = out_dir.parent / f".tmp-{day.isoformat()}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_parquet = tmp_dir / PREDICTIONS_NAME
    pq.write_table(table, tmp_parquet, compression="snappy")
    manifest = {
        "schema_version": SCORES_SCHEMA_VERSION,
        "kind": "scores",
        "model_release_id": pinned.model_release_id,
        "mlflow_model_version": pinned.manifest["mlflow_model_version"],
        "data_release_id": pinned.manifest["data_release_id"],
        "feature_release_id": feature_release_id,
        "feature_manifest_sha256": sha256_file(Path(features_dir) / "manifest.json"),
        "git_sha": pinned.manifest["source_commit"],
        "issue_date": day.isoformat(),
        "issue_time_utc": _iso_us(issue_us),
        "target_window": {
            "start": _iso_us(int(target_us.min())),
            "end": _iso_us(int(target_us.max())),
        },
        "rows": int(len(preds)),
        "stations": int(np.unique(stations).size),
        "predictions": {
            "path": PREDICTIONS_NAME,
            "sha256": sha256_file(tmp_parquet),
            "size_bytes": tmp_parquet.stat().st_size,
        },
    }

    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        reused = existing == manifest
        if not reused:
            tmp_parquet.unlink(missing_ok=True)
            tmp_dir.rmdir()
            raise RuntimeError(
                f"score collision: {manifest_path} exists with different content; "
                "cut a new model release instead of overwriting a scored issue day"
            )
    else:
        reused = False
        out_dir.mkdir(parents=True, exist_ok=True)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_parquet.replace(parquet_path)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    tmp_parquet.unlink(missing_ok=True)
    tmp_dir.rmdir()
    return {"manifest": manifest, "reused": reused, "manifest_path": manifest_path}


# -- shadow comparison --------------------------------------------------------------


def shadow_compare(
    pinned: Release,
    candidate: Release,
    release_dir: Path,
    cfg: dict,
    features_dir: Path,
    issue_days: list[str | date],
    *,
    out_path: Path | None = None,
) -> dict:
    """Score the same request set with candidate and pinned side by side,
    offline: per issue day the pooled candidate−pinned deltas and, where
    labels are readable, both models' MAE."""
    _feature_release_guard(pinned, features_dir)
    _feature_release_guard(candidate, features_dir)
    days = [date.fromisoformat(d) if isinstance(d, str) else d for d in issue_days]
    if not days:
        raise ValueError("shadow comparison needs at least one issue day")
    request_hash = hashlib.sha256(
        json.dumps(
            {
                "candidate": candidate.model_release_id,
                "pinned": pinned.model_release_id,
                "issue_days": [d.isoformat() for d in days],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    per_day = []
    stations_of_set: np.ndarray | None = None
    for day in days:
        stations, target_us, preds_p, data = _predict_day(
            pinned, release_dir, cfg, features_dir, day
        )
        if stations_of_set is None:
            stations_of_set = stations
        candidate_pipe = candidate.pipeline
        preds_c = candidate_pipe.predict(data.X)
        delta = np.abs(preds_c - preds_p)
        labeled = np.isfinite(data.y)
        entry = {
            "issue_date": day.isoformat(),
            "rows": int(len(preds_p)),
            "mean_abs_delta": _round(float(delta.mean())),
            "max_abs_delta": _round(float(delta.max())),
            "pinned_mae": _round(float(np.abs(preds_p[labeled] - data.y[labeled]).mean()))
            if labeled.any()
            else None,
            "candidate_mae": _round(float(np.abs(preds_c[labeled] - data.y[labeled]).mean()))
            if labeled.any()
            else None,
        }
        per_day.append(entry)

    report = {
        "schema_version": SHADOW_SCHEMA_VERSION,
        "kind": "shadow-comparison",
        "pinned": {
            "model_release_id": pinned.model_release_id,
            "mlflow_model_version": pinned.manifest["mlflow_model_version"],
            "manifest_sha256": pinned.manifest_sha256,
        },
        "candidate": {
            "model_release_id": candidate.model_release_id,
            "mlflow_model_version": candidate.manifest["mlflow_model_version"],
            "manifest_sha256": candidate.manifest_sha256,
        },
        "request_set": {
            "issue_days": [d.isoformat() for d in days],
            "stations": int(np.unique(stations_of_set).size),
            "hours_per_issue": TARGET_HOURS,
            "hash": request_hash,
        },
        "per_issue_day": per_day,
        "overall": {
            "mean_abs_delta": _round(float(np.mean([e["mean_abs_delta"] for e in per_day]))),
            "max_abs_delta": _round(float(max(e["max_abs_delta"] for e in per_day))),
        },
    }
    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
