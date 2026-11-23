"""The idempotent district pipeline and its release gate (M09 domain code).

`run-pipeline` executes validate → dataset → features → baselines →
train → publish in sequence. Each step reuses its existing output when
the current inputs still match it (content comparison, checked not
claimed); different content under the same release id is a collision.
The publish gate refuses a candidate whose pooled protocol MAE does not
strictly beat both committed baselines; refusals leave the pin — here,
the reference workload's serving pin — untouched.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np

from . import dataset as dataset_mod
from .baselines import run_baselines
from .features import build_features
from .model import MODEL_CONFIG, design_matrix, fit_model, load_features, protocol_metrics
from .releases import git_commit, publish_release, read_json, sha256_file

GATE_BASELINES = ("district_seasonal_naive", "district_median")


def step_dataset(cfg: dict, source_release: Path, out_release: Path) -> dict:
    out_release = Path(out_release)
    source_sha = sha256_file(Path(source_release) / "manifest.json")
    marker = out_release / "_SUCCESS"
    if marker.exists():
        manifest = read_json(out_release / "manifest.json")
        if manifest["lineage"]["source_manifest_sha256"] == source_sha:
            return {**manifest, "reused": True}
        raise FileExistsError(
            f"dataset release {manifest['release_id']} was built from a different "
            f"source release; choose a new release id"
        )
    built = dataset_mod.build_dataset(cfg, source_release, out_release)
    checks = dataset_mod.validate_dataset(cfg, out_release)
    return {**built, "checks": checks, "reused": False}


def step_features(cfg: dict, dataset_dir: Path, out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    dataset_sha = sha256_file(Path(dataset_dir) / "manifest.json")
    manifest_path = out_dir / "manifest.json"
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        if manifest["source_manifest_sha256"] == dataset_sha:
            return {**manifest, "reused": True}
        raise FileExistsError(
            f"feature release {manifest['feature_release_id']} was built from a "
            f"different dataset; choose a new release id"
        )
    return {**build_features(cfg, dataset_dir, out_dir), "reused": False}


def step_baselines(cfg: dict, dataset_dir: Path, out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    dataset_sha = sha256_file(Path(dataset_dir) / "manifest.json")
    report_path = out_dir / "baseline-report.json"
    if report_path.exists():
        report = read_json(report_path)
        if report["source_manifest_sha256"] == dataset_sha:
            return {**report, "reused": True}
        raise FileExistsError("baseline report was built from a different dataset; move it aside")
    return run_baselines(cfg, dataset_dir, out_dir)


def candidate_id(data_sha: str, feature_sha: str, commit: str) -> str:
    raw = json.dumps([data_sha, feature_sha, commit])
    return "model-district-" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def step_train(cfg: dict, dataset_dir: Path, features_dir: Path, out_reports: Path) -> dict:
    """Protocol training with reuse: identical inputs return the committed
    protocol result instead of refitting."""
    out_reports = Path(out_reports)
    data_sha = sha256_file(Path(dataset_dir) / "manifest.json")
    feature_sha = sha256_file(Path(features_dir) / "manifest.json")
    commit = git_commit(out_reports)
    candidate = candidate_id(data_sha, feature_sha, commit)
    result_path = out_reports / candidate / "protocol.json"
    if result_path.exists():
        return {**read_json(result_path), "candidate_id": candidate, "reused": True}
    protocol = protocol_metrics(cfg, features_dir)
    preds, labels = protocol.pop("preds"), protocol.pop("labels")
    out = out_reports / candidate
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / "preds.npy", preds)
    np.save(out / "labels.npy", labels)
    (result_path).write_text(
        json.dumps(protocol, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {**protocol, "candidate_id": candidate, "reused": False}


def promotion_gate(protocol: dict, baselines: dict) -> None:
    """Refuse a candidate that does not strictly beat both baselines pooled."""
    model_mae = protocol["pooled"]["mae"]
    refused = [
        name
        for name in GATE_BASELINES
        if baselines["results"][name]["overall"]["mae"] is None
        or not model_mae < baselines["results"][name]["overall"]["mae"]
    ]
    if refused:
        raise ValueError(
            f"promotion gate refused candidate {protocol['candidate_id']}: MAE "
            f"{model_mae} does not strictly beat " + ", ".join(refused)
        )


def run_pipeline(
    cfg: dict,
    source_release: Path,
    paths: dict[str, Path],
) -> dict:
    """validate → dataset → features → baselines → train → gate → publish."""
    source_release = Path(source_release)
    if not (source_release / "_SUCCESS").exists():
        raise ValueError(f"source release not published: {source_release}")

    dataset_manifest = step_dataset(cfg, source_release, paths["dataset"])
    feature_manifest = step_features(cfg, paths["dataset"], paths["features"])
    baselines = step_baselines(cfg, paths["dataset"], paths["baselines"])
    protocol = step_train(cfg, paths["dataset"], paths["features"], paths["reports"])
    promotion_gate(protocol, baselines)

    data_sha = sha256_file(paths["dataset"] / "manifest.json")
    feature_sha = sha256_file(paths["features"] / "manifest.json")
    commit = git_commit(paths["models"])
    candidate = protocol["candidate_id"]
    releases_dir = Path(paths["releases"]) / candidate
    manifest_path = releases_dir / "manifest.json"
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        if (
            manifest["data_manifest_sha256"] == data_sha
            and manifest["feature_manifest_sha256"] == feature_sha
            and manifest["artifact"]["sha256"]
            == sha256_file(Path(paths["models"]) / candidate / "model.joblib")
        ):
            return {
                "release_id": candidate,
                "manifest": manifest,
                "reused": True,
                "dataset_reused": dataset_manifest["reused"],
                "features_reused": feature_manifest["reused"],
                "baselines_reused": baselines["reused"],
                "training_reused": protocol["reused"],
            }
        raise FileExistsError(f"model release {candidate} exists with different content")

    models_dir = Path(paths["models"]) / candidate
    models_dir.mkdir(parents=True, exist_ok=True)
    artifact = models_dir / "model.joblib"
    table = load_features(paths["features"])
    X = design_matrix(table, list(cfg["districts"]))
    y = np.array(table["demand_kwh"].to_pylist(), dtype=float)
    finite = np.isfinite(X).all(axis=1) & np.isfinite(y)
    model = fit_model(X[finite], y[finite])  # the deployment model: refit on every labeled row
    joblib.dump(model, artifact, compress=3)

    manifest = {
        "release_id": candidate,
        "kind": "model",
        "model_config": MODEL_CONFIG,
        "metrics": protocol["pooled"],
        "fold_plan": protocol["fold_plan"],
        "data_manifest_sha256": data_sha,
        "data_release_id": dataset_manifest["release_id"],
        "feature_release_id": feature_manifest["feature_release_id"],
        "feature_manifest_sha256": feature_sha,
        "source_commit": commit,
        "artifact": {
            "path": "model.joblib",
            "sha256": sha256_file(artifact),
            "size_bytes": artifact.stat().st_size,
        },
        "gate": {
            "baselines": {
                name: baselines["results"][name]["overall"]["mae"] for name in GATE_BASELINES
            },
            "decision": "promoted",
        },
    }
    publish_release(releases_dir, manifest)
    return {
        "release_id": candidate,
        "manifest": manifest,
        "reused": False,
        "dataset_reused": dataset_manifest["reused"],
        "features_reused": feature_manifest["reused"],
        "baselines_reused": baselines["reused"],
        "training_reused": protocol["reused"],
    }
