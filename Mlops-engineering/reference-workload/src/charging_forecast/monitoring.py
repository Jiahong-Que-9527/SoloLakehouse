"""Calibrate and evaluate the M07 monitors on complete M06 scoring days."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from http.client import HTTPConnection
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from .contract import sha256_file
from .eval import US_HOUR, build_folds, error_metrics, load_demand, target_hours_us
from .features import load_training_features
from .serving import PREDICTIONS_NAME, Release
from .training import CAT_FEATURES, build_training_data

SCHEMA_VERSION = "charging-monitor-v1"
FAMILIES = {
    "station": ("district", "poi_category", "capacity_kw", "days_active"),
    "calendar": ("hour_of_day", "day_of_week", "is_public_holiday", "is_school_break"),
    "demand": ("demand_lag_24h", "demand_lag_168h", "demand_rolling_7d_mean", "demand_latest"),
    "weather": ("fcst_temperature_c", "fcst_precipitation_mm"),
    "tariff": ("price_current", "price_at_target"),
    "event": ("event_boost", "is_event_active"),
    "prediction": ("predicted_kwh",),
}
CATEGORICAL = {*CAT_FEATURES, *FAMILIES["calendar"], "is_event_active"}
MIN_RESIDUAL_ROWS = 100
RETRAIN_DAYS = 30


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        temp_path = Path(tmp.name)
        try:
            json.dump(value, tmp, indent=2, sort_keys=True, allow_nan=False)
            tmp.write("\n")
            tmp.flush()
            temp_path.replace(path)
        finally:
            temp_path.unlink(missing_ok=True)


def _distribution(values: np.ndarray, spec: dict) -> tuple[np.ndarray, np.ndarray, float]:
    if "categories" in spec:
        counts = np.array([np.count_nonzero(values == c) for c in spec["categories"]])
        missing = sum(value is None for value in values) if values.dtype == object else 0
        buckets = np.r_[counts, len(values) - counts.sum() - missing, missing]
        sample = np.array([])
    else:
        sample = np.sort(values[np.isfinite(values)])
        missing = len(values) - len(sample)
        bins = np.searchsorted(spec["cuts"], sample, side="right")
        buckets = np.r_[np.bincount(bins, minlength=len(spec["cuts"]) + 1), missing]
    return buckets / len(values), sample, float(missing / len(values))


def _reference(values: np.ndarray, categorical: bool) -> dict:
    if categorical:
        spec = {"categories": sorted(set(values.tolist()) - {None})}
    else:
        finite = values[np.isfinite(values)]
        cuts = np.unique(np.quantile(finite, np.arange(1, 10) / 10)).tolist() if finite.size else []
        spec = {"cuts": cuts}
    proportions, sample, _ = _distribution(values, spec)
    if sample.size:
        indices = np.linspace(0, len(sample) - 1, min(len(sample), 4096), dtype=int)
        spec["sample"] = sample[indices].tolist()
    return {**spec, "proportions": proportions.tolist()}


def _signals(frame, predictions: np.ndarray, reference: dict, labels: np.ndarray) -> dict:
    signals = {}
    for family, columns in FAMILIES.items():
        for column in columns:
            values = predictions if family == "prediction" else frame[column].to_numpy()
            spec = reference[column]
            observed, sample, missing = _distribution(values, spec)
            expected = np.maximum(spec["proportions"], 1e-4)
            observed = np.maximum(observed, 1e-4)
            prefix = f"{family}.{column}"
            signals[f"{prefix}.psi"] = float(
                np.sum((observed - expected) * np.log(observed / expected))
            )
            signals[f"{prefix}.missing"] = missing
            if "sample" in spec:
                ks = None
                if sample.size:
                    ref = np.asarray(spec["sample"])
                    points = np.r_[ref, sample]
                    ref_cdf = np.searchsorted(ref, points, side="right") / len(ref)
                    obs_cdf = np.searchsorted(sample, points, side="right") / len(sample)
                    ks = float(np.max(np.abs(ref_cdf - obs_cdf)))
                signals[f"{prefix}.ks"] = ks
    errors = error_metrics(predictions, labels)
    signals["residual.mae_kwh"] = errors["mae"] if errors["n"] >= MIN_RESIDUAL_ROWS else None
    return signals


def _input_identity(release_dir: Path, features_dir: Path) -> dict:
    data_hash = sha256_file(release_dir / "manifest.json")
    feature_path = features_dir / "manifest.json"
    features = read_json(feature_path)
    if features["source_manifest_sha256"] != data_hash:
        raise ValueError("features and demand are from different dataset manifests")
    return {
        "data_release_id": read_json(release_dir / "manifest.json")["release_id"],
        "data_manifest_sha256": data_hash,
        "feature_manifest_sha256": sha256_file(feature_path),
        "feature_release_id": features["feature_release_id"],
    }


def calibrate(
    pinned: Release, release_dir: Path, cfg: dict, features_dir: Path, baseline_path: Path
) -> dict:
    """Use M03's monthly issue ranges, with earlier folds as the reference."""
    identity = _input_identity(release_dir, features_dir)
    if any(pinned.manifest[key] != identity[key] for key in identity):
        raise ValueError("calibration inputs must match the pinned model training lineage")
    baseline = read_json(baseline_path)
    if (
        baseline["source_manifest_sha256"] != identity["data_manifest_sha256"]
        or baseline["feature_manifest_sha256"] != identity["feature_manifest_sha256"]
    ):
        raise ValueError("the M03 report must describe the calibration dataset and features")
    folds, _ = build_folds(cfg)
    expected_ranges = [(f.issue_start.isoformat(), f.issue_end.isoformat()) for f in folds]
    observed_ranges = [(f["issue_start"], f["issue_end"]) for f in baseline["fold_plan"]["folds"]]
    if expected_ranges != observed_ranges or len(folds) < 2:
        raise ValueError("calibration requires the matching M03 rolling-origin fold report")
    first, last = folds[0].issue_start, folds[-1].issue_end
    days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    table = load_training_features(features_dir, first, last)
    demand = load_demand(release_dir, cfg)
    data = build_training_data(table, demand, days)
    pred = np.round(pinned.pipeline.predict(data.X), 6)
    split = (folds[len(folds) // 2].issue_start - first).days
    ref_mask = data.issue_idx < split
    reference = {}
    for family, columns in FAMILIES.items():
        for column in columns:
            values = pred if family == "prediction" else data.X[column].to_numpy()
            reference[column] = _reference(values[ref_mask], column in CATEGORICAL)

    thresholds = {}
    for index in range(split, len(days)):
        rows = data.issue_idx == index
        if not rows.any():
            raise ValueError(f"calibration has no feature rows for {days[index]}")
        measurements = _signals(data.X.loc[rows], pred[rows], reference, data.y[rows])
        for signal, value in measurements.items():
            if value is None:
                continue
            entry = thresholds.setdefault(signal, {"observed_max": -1.0, "windows": 0})
            entry["windows"] += 1
            if value > entry["observed_max"]:
                entry.update(observed_max=value, issue_date=days[index].isoformat())
    pooled_mae = pinned.manifest["metrics"]["model_mae"]
    for signal, entry in thresholds.items():
        floor = pooled_mae if signal == "residual.mae_kwh" else 0.0
        entry["limit"] = max(entry["observed_max"], floor)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "monitor-calibration",
        **identity,
        "model_release_id": pinned.model_release_id,
        "model_manifest_sha256": pinned.manifest_sha256,
        "m03_report_sha256": sha256_file(baseline_path),
        "m03_folds": len(folds),
        "model_pooled_backtest_mae_kwh": pooled_mae,
        "reference_start": first.isoformat(),
        "reference_end": days[split - 1].isoformat(),
        "reference_rows": int(ref_mask.sum()),
        "calibration_start": days[split].isoformat(),
        "calibration_end": last.isoformat(),
        "threshold_method": (
            "max across 24-hour calibration windows; residual floor is model backtest MAE"
        ),
        "reference": reference,
        "thresholds": thresholds,
    }


def _score_predictions(
    pinned: Release, identity: dict, day: date, table: pa.Table, path: Path, manifest_path: Path
) -> np.ndarray:
    manifest = read_json(manifest_path)
    expected = {
        "model_release_id": pinned.model_release_id,
        "mlflow_model_version": pinned.manifest["mlflow_model_version"],
        "data_release_id": pinned.manifest["data_release_id"],
        "git_sha": pinned.manifest["source_commit"],
        "feature_release_id": identity["feature_release_id"],
        "feature_manifest_sha256": identity["feature_manifest_sha256"],
        "issue_date": day.isoformat(),
    }
    if any(manifest[key] != value for key, value in expected.items()):
        raise ValueError("score manifest does not match the monitored window and lineage")
    if path.name != PREDICTIONS_NAME or sha256_file(path) != manifest["predictions"]["sha256"]:
        raise ValueError("score Parquet does not match its manifest checksum")
    scores = pq.read_table(path)
    if len(scores) != manifest["rows"]:
        raise ValueError("score manifest row count differs from Parquet")
    score_hours = scores["target_time"].cast(pa.int64()).to_numpy()
    keys = list(zip(scores["station_id"].to_pylist(), score_hours, strict=True))
    predictions = dict(zip(keys, scores["predicted_kwh"].to_numpy(), strict=True))
    hours = table["hour_utc"].cast(pa.int64()).to_numpy()
    requested = list(zip(table["station_id"].to_pylist(), hours, strict=True))
    expected_keys = set(requested)
    stations = set(table["station_id"].to_pylist())
    target_hours = set(target_hours_us(day))
    if (
        set(keys) != expected_keys
        or len(keys) != len(expected_keys)
        or len(requested) != len(expected_keys)
        or not set(hours) <= target_hours
        or len(stations) != manifest["stations"]
        or len(expected_keys) != len(stations) * len(target_hours)
    ):
        raise ValueError("features and scores must contain identical, unique target keys")
    values = np.asarray([predictions[key] for key in requested])
    if not np.isfinite(values).all():
        raise ValueError("score predictions must be finite")
    return values


def evaluate(
    pinned: Release,
    release_dir: Path,
    cfg: dict,
    features_dir: Path,
    day: date,
    calibration: dict,
    score_path: Path,
    score_manifest: Path,
    *,
    as_of: datetime,
) -> dict:
    """Evaluate the latest 24-hour score window and use only mature labels."""
    if as_of.utcoffset() is None:
        raise ValueError("as-of requires a timezone")
    as_of = as_of.astimezone(UTC)
    if (
        calibration["schema_version"] != SCHEMA_VERSION
        or calibration["model_manifest_sha256"] != pinned.manifest_sha256
    ):
        raise ValueError("calibration does not match the pinned model release")
    identity = _input_identity(release_dir, features_dir)
    table = load_training_features(features_dir, day, day)
    cutoff_us = int(as_of.timestamp() * 1_000_000)
    if cutoff_us < int(table["available_at"].cast(pa.int64()).to_numpy().max()):
        raise ValueError("as-of precedes the forecast issue time")
    demand = load_demand(release_dir, cfg)
    for station in demand.stations:
        demand.values[station] = np.where(
            demand.avail[station] <= cutoff_us, demand.values[station], np.nan
        )
    data = build_training_data(table, demand, [day])
    pred = _score_predictions(pinned, identity, day, table, score_path, score_manifest)
    measurements = _signals(data.X, pred, calibration["reference"], data.y)
    delay = int(cfg.get("ingestion_delay_hours", 1))
    last_label_us = int(target_hours_us(day)[-1]) + (1 + delay) * US_HOUR
    if cutoff_us < last_label_us:
        measurements["residual.mae_kwh"] = None
    signals = {
        name: {
            "value": value,
            "limit": limit,
            "breached": value is not None and limit is not None and value > limit + 1e-12,
        }
        for name, value in measurements.items()
        for limit in [calibration["thresholds"].get(name, {}).get("limit")]
    }
    labeled = int(np.isfinite(data.y).sum())
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "monitor-window",
        **identity,
        "model_release_id": pinned.model_release_id,
        "model_manifest_sha256": pinned.manifest_sha256,
        "score_manifest_sha256": sha256_file(score_manifest),
        "issue_date": day.isoformat(),
        "as_of": as_of.isoformat(),
        "scored_rows": len(pred),
        "labeled_rows": labeled,
        "label_coverage": labeled / len(pred),
        "signals": signals,
    }


def retraining_decision(
    report: dict, *, last_training: date | None = None, manual_reason: str | None = None
) -> dict:
    """Record every reason, separating missing inputs from a training trigger."""
    as_of = datetime.fromisoformat(report["as_of"]).date()
    if last_training is not None and last_training > as_of:
        raise ValueError("last training date follows the evaluation date")
    breaches = sorted(name for name, signal in report["signals"].items() if signal["breached"])
    input_incidents = [name for name in breaches if name.endswith(".missing")]
    drift = sorted(set(breaches) - set(input_incidents))
    if manual_reason is not None and not manual_reason.strip():
        raise ValueError("manual override requires a reason")
    reasons = {}
    if input_incidents:
        reasons["input_quality"] = input_incidents
    if drift:
        reasons["drift"] = drift
    if last_training is not None and (as_of - last_training).days >= RETRAIN_DAYS:
        reasons["calendar"] = {"last_training": last_training.isoformat(), "days": RETRAIN_DAYS}
    if manual_reason is not None:
        reasons["manual"] = manual_reason.strip()
    should_retrain = manual_reason is not None or (bool(reasons) and not input_incidents)
    record = {
        "action": "retrain" if should_retrain else "hold",
        "reasons": reasons,
        "model_release_id": report["model_release_id"],
        "model_manifest_sha256": report["model_manifest_sha256"],
        "data_manifest_sha256": report["data_manifest_sha256"],
        "issue_date": report["issue_date"],
    }
    decision_id = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
    return {**record, "decision_id": decision_id, "as_of": report["as_of"]}


def push_metrics(report: dict, gateway: str) -> None:
    """Replace one local Pushgateway group so prior windows cannot stay firing."""
    endpoint = urlsplit(gateway)
    if (
        endpoint.scheme != "http"
        or endpoint.hostname not in {"127.0.0.1", "localhost", "::1"}
        or endpoint.username is not None
        or endpoint.path not in {"", "/"}
        or endpoint.query
        or endpoint.fragment
    ):
        raise ValueError("Pushgateway must be a local HTTP origin")
    model = json.dumps(report["model_release_id"], ensure_ascii=False)
    lines = [f"charging_monitor_label_coverage{{model_release={model}}} {report['label_coverage']}"]
    for name, signal in sorted(report["signals"].items()):
        labels = f"model_release={model},signal={json.dumps(name)}"
        lines.append(f"charging_monitor_breach{{{labels}}} {int(signal['breached'])}")
        for key in ("value", "limit"):
            if signal[key] is not None:
                lines.append(f"charging_monitor_{key}{{{labels}}} {signal[key]}")
    connection = HTTPConnection(endpoint.hostname, endpoint.port, timeout=5)
    try:
        connection.request(
            "PUT",
            "/metrics/job/charging_forecast_monitor",
            body=("\n".join(lines) + "\n").encode(),
            headers={"Content-Type": "text/plain; version=0.0.4"},
        )
        response = connection.getresponse()
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Pushgateway returned HTTP {response.status}")
    finally:
        connection.close()
