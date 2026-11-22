"""Training pipeline, registry and release gate (M05).

Implements the resolved M05 decisions (docs/delivery-plan.md, M05 entry):
one idempotent CLI sequence — validate, features, train, evaluate, register,
publish — where every step is a no-op when its existing output already
matches the current inputs (idempotence by content comparison, not by
claim), plus the promotion primitives `pin-model` and `verify-pin`.

The release shape follows ADR-005 and the ADR-003 manifest pattern: the
deterministic `model.joblib` artifact (fitted selected config over every
labeled feature row) lives outside Git under `data/models/<release_id>/`,
while `releases/models/<release_id>/manifest.json` and
`releases/models/pinned.json` are committed. The MLflow registry
(`charging_demand_forecast`, local sqlite store) is lineage only — the pin
is the manifest, so serving reads `pinned.json`, never a registry alias.
Promotion through `pin-model` is gated: a candidate must strictly beat the
pinned release's pooled protocol MAE (the first pin must beat both
committed M03 baselines), and refused promotions leave the pin untouched.

The manifest is written once per release: reruns reproduce the same
registry IDs (the register step reuses an existing version tagged with the
release ID), so republishing yields byte-identical manifests and changes
nothing. A manifest that already exists with different content is a
release-ID collision and fails loudly instead of being overwritten.
"""

from __future__ import annotations

import os

os.environ.setdefault("OMP_NUM_THREADS", "1")  # before sklearn loads: pin threads for determinism

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import joblib
import mlflow
import numpy as np
from mlflow.tracking import MlflowClient

from .contract import git_commit, sha256_file
from .eval import load_demand, valid_issue_range
from .features import FEATURES_SCHEMA_VERSION, FeatureBuilder, load_training_features
from .training import (
    DEFAULT_TRACKING_URI,
    GRID,
    MAX_ITER,
    RANDOM_SEED,
    SEL_TRAIN_END,
    SEL_VAL_END,
    SEL_VAL_START,
    TARGET_HOURS,
    build_training_data,
    make_pipeline,
    run_model_training,
)
from .validation import validate_release

MODEL_RELEASE_SCHEMA_VERSION = "charging-model-release-v1"
REGISTRY_MODEL_NAME = "charging_demand_forecast"
RELEASE_STAGE_CANDIDATE = "candidate"
RELEASE_STAGE_REGISTERED = "registered"
RELEASE_STAGE_PINNED = "pinned"
DEFAULT_RELEASES_DIR = Path("releases/models")
DEFAULT_MODELS_DIR = Path("data/models")
DEFAULT_MODEL_RELEASE_ID = "model-v001"
ARTIFACT_NAME = "model.joblib"


def _round(x: float) -> float:
    return round(float(x), 6)


# -- artifact ------------------------------------------------------------------


def write_model_artifact(pipe, models_dir: Path, model_release_id: str) -> tuple[Path, dict]:
    """Serialize the fitted pipeline deterministically (compressed pickle) and
    return (path, artifact entry with checksum)."""
    path = Path(models_dir) / model_release_id / ARTIFACT_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, path, compress=3)
    return path, {
        "path": ARTIFACT_NAME,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


# -- steps -------------------------------------------------------------------


def step_validate(release_dir: Path, cfg: dict) -> dict:
    """Run the dataset validation suite; any failing check stops the pipeline."""
    results = validate_release(Path(release_dir), cfg)
    failed = [c for c in results if not c.passed]
    if failed:
        details = "; ".join(f"{c.name}: {c.detail}" for c in failed)
        raise RuntimeError(f"validation failed ({len(failed)} checks): {details}")
    return {"checks": len(results), "failed": 0}


def _features_identity(features_dir: Path) -> dict | None:
    path = Path(features_dir) / "manifest.json"
    if not path.exists():
        return None
    m = json.loads(path.read_text(encoding="utf-8"))
    return {
        "feature_release_id": m.get("feature_release_id"),
        "source_manifest_sha256": m.get("source_manifest_sha256"),
        "issue_start": m.get("issue_start"),
        "issue_end": m.get("issue_end"),
    }


def step_features(release_dir: Path, cfg: dict, features_dir: Path) -> dict:
    """Materialize point-in-time features over the full valid issue range,
    or reuse the existing materialization when its identity matches."""
    release_dir, features_dir = Path(release_dir), Path(features_dir)
    v_start, v_end = valid_issue_range(cfg)
    major = FEATURES_SCHEMA_VERSION.rsplit("-v", 1)[-1]
    expected = {
        "feature_release_id": f"feat-v{major}-{cfg['release_id']}",
        "source_manifest_sha256": sha256_file(Path(release_dir) / "manifest.json"),
        "issue_start": v_start.isoformat(),
        "issue_end": v_end.isoformat(),
    }
    if _features_identity(features_dir) == expected:
        return {"reused": True, **expected}
    FeatureBuilder(release_dir, cfg).materialize(v_start, v_end, features_dir)
    if _features_identity(features_dir) != expected:
        raise RuntimeError("feature materialization does not match the expected identity")
    return {"reused": False, **expected}


def _current_identity(
    release_dir: Path,
    features_dir: Path,
    *,
    max_iter: int,
    seed: int,
    grid: dict[str, list] | None,
    sel: tuple[date, date, date],
) -> dict:
    """Identity of the pipeline inputs: the dataset manifest's config hash,
    the feature manifest hash, the code commit and the training budget."""
    manifest = json.loads((Path(release_dir) / "manifest.json").read_text(encoding="utf-8"))
    return {
        "source_config_sha256": manifest["config_sha256"],
        "feature_manifest_sha256": sha256_file(Path(features_dir) / "manifest.json"),
        "source_commit": git_commit(Path(release_dir)),
        "max_iter": max_iter,
        "seed": seed,
        "grid": {k: list(v) for k, v in (grid or GRID).items()},
        "selection": [d.isoformat() for d in sel],
    }


def _report_identity(report: dict) -> dict:
    sel = report["selection"]["split"]
    return {
        "source_config_sha256": report["source_config_sha256"],
        "feature_manifest_sha256": report["feature_manifest_sha256"],
        "source_commit": report["source_commit"],
        "max_iter": report["model"]["max_iter"],
        "seed": report["model"]["seed"],
        "grid": {k: list(v) for k, v in report["selection"]["grid"].items()},
        "selection": [
            sel["train_end"],
            sel["val_start"],
            sel["val_end"],
        ],
    }


def step_train(
    release_dir: Path,
    cfg: dict,
    features_dir: Path,
    out_dir: Path,
    model_release_id: str,
    models_dir: Path,
    *,
    tracking_uri: str = DEFAULT_TRACKING_URI,
    max_iter: int = MAX_ITER,
    seed: int = RANDOM_SEED,
    grid: dict[str, list] | None = None,
    sel_train_end: date = SEL_TRAIN_END,
    sel_val_start: date = SEL_VAL_START,
    sel_val_end: date = SEL_VAL_END,
) -> tuple[dict, Path, bool]:
    """Run the M04 grid selection + protocol (or reuse the report when its
    identity matches), then ensure the release artifact exists: the selected
    config refit on every labeled feature row. Returns (report, artifact
    path, reused)."""
    release_dir, features_dir, out_dir, models_dir = (
        Path(release_dir),
        Path(features_dir),
        Path(out_dir),
        Path(models_dir),
    )
    report_path = out_dir / "model-report.json"
    current = _current_identity(
        release_dir,
        features_dir,
        max_iter=max_iter,
        seed=seed,
        grid=grid,
        sel=(sel_train_end, sel_val_start, sel_val_end),
    )
    reused = False
    if report_path.exists():
        existing = json.loads(report_path.read_text(encoding="utf-8"))
        if _report_identity(existing) == current:
            report = existing
            reused = True
    if not reused:
        report = run_model_training(
            release_dir,
            cfg,
            features_dir,
            out_dir,
            tracking_uri=tracking_uri,
            max_iter=max_iter,
            seed=seed,
            grid=grid,
            sel_train_end=sel_train_end,
            sel_val_start=sel_val_start,
            sel_val_end=sel_val_end,
        )

    artifact_path = models_dir / model_release_id / ARTIFACT_NAME
    if not artifact_path.exists():
        demand = load_demand(release_dir, cfg)
        v_start, v_end = valid_issue_range(cfg)
        issue_days = [v_start + timedelta(days=i) for i in range((v_end - v_start).days + 1)]
        table = load_training_features(features_dir, v_start, v_end)
        data = build_training_data(table, demand, issue_days)
        labeled = np.isfinite(data.y)
        pipe = make_pipeline(report["model"]["selected_config"], max_iter=max_iter, seed=seed)
        pipe.fit(data.X.loc[labeled], data.y[labeled])
        write_model_artifact(pipe, models_dir, model_release_id)
    return report, artifact_path, reused


def step_evaluate(report: dict) -> dict:
    """The evaluate step: the candidate must beat both committed baselines;
    the promotion gate on top of this compares against the pinned release."""
    acc = report["acceptance"]
    if not (acc["beats_seasonal_naive"] and acc["beats_station_median"]):
        raise RuntimeError(
            f"evaluate failed: model MAE {acc['model_mae']} does not beat both baselines "
            f"(naive {acc['gate_mae']}, median {acc['median_mae']})"
        )
    return {
        "model_mae": acc["model_mae"],
        "gate_mae": acc["gate_mae"],
        "median_mae": acc["median_mae"],
        "beats_baselines": True,
    }


def _client(tracking_uri: str) -> MlflowClient:
    mlflow.set_tracking_uri(tracking_uri)
    return MlflowClient(tracking_uri=tracking_uri)


def find_registry_version(client: MlflowClient, model_release_id: str):
    versions = client.search_model_versions(
        f"name='{REGISTRY_MODEL_NAME}' and tags.model_release_id='{model_release_id}'"
    )
    if not versions:
        return None
    return max(versions, key=lambda v: int(v.version))


def step_register(
    release_dir: Path,
    features_dir: Path,
    report: dict,
    artifact_path: Path,
    model_release_id: str,
    *,
    tracking_uri: str = DEFAULT_TRACKING_URI,
) -> dict:
    """Log the release artifact to MLflow and register the model version
    (idempotent: an existing version tagged with the release ID is reused)."""
    client = _client(tracking_uri)
    existing = find_registry_version(client, model_release_id)
    if existing is not None:
        return {
            "created": False,
            "version": int(existing.version),
            "run_id": existing.run_id,
        }

    manifest = json.loads((Path(release_dir) / "manifest.json").read_text(encoding="utf-8"))
    fmanifest = json.loads((Path(features_dir) / "manifest.json").read_text(encoding="utf-8"))
    pipe = joblib.load(artifact_path)
    with mlflow.start_run(run_name=f"release-{model_release_id}") as run:
        mlflow.log_artifact(str(artifact_path), artifact_path="release")
        model_info = mlflow.sklearn.log_model(
            pipe,
            name="model",
            registered_model_name=REGISTRY_MODEL_NAME,
            # Our own fit output; skops only flags the HistGB tree predictor.
            skops_trusted_types=[
                "sklearn.ensemble._hist_gradient_boosting.predictor.TreePredictor"
            ],
        )
        mlflow.set_tags(
            {
                "stage": "m05",
                "model_release_id": model_release_id,
                "data_release_id": manifest["release_id"],
                "feature_release_id": fmanifest["feature_release_id"],
                "git_sha": report["source_commit"],
                "run_kind": "release",
            }
        )
    version_number = model_info.registered_model_version
    if version_number is None:
        raise RuntimeError("model version registration did not produce a version")
    for key, value in (
        ("model_release_id", model_release_id),
        ("data_release_id", manifest["release_id"]),
        ("feature_release_id", fmanifest["feature_release_id"]),
        ("git_sha", report["source_commit"]),
        ("release_stage", RELEASE_STAGE_CANDIDATE),
    ):
        client.set_model_version_tag(REGISTRY_MODEL_NAME, version_number, key, value)
    return {"created": True, "version": int(version_number), "run_id": run.info.run_id}


def build_release_manifest(
    release_dir: Path,
    features_dir: Path,
    report: dict,
    artifact_path: Path,
    model_release_id: str,
    registry_info: dict,
) -> dict:
    manifest = json.loads((Path(release_dir) / "manifest.json").read_text(encoding="utf-8"))
    fmanifest = json.loads((Path(features_dir) / "manifest.json").read_text(encoding="utf-8"))
    return {
        "schema_version": MODEL_RELEASE_SCHEMA_VERSION,
        "model_release_id": model_release_id,
        "kind": "model",
        "registered_model_name": REGISTRY_MODEL_NAME,
        "mlflow_model_version": registry_info["version"],
        "source_run_id": registry_info["run_id"],
        "source_commit": report["source_commit"],
        "data_release_id": manifest["release_id"],
        "data_manifest_sha256": sha256_file(Path(release_dir) / "manifest.json"),
        "feature_release_id": fmanifest["feature_release_id"],
        "feature_manifest_sha256": sha256_file(Path(features_dir) / "manifest.json"),
        "model_config": report["model"]["selected_config"],
        "max_iter": report["model"]["max_iter"],
        "seed": report["model"]["seed"],
        "metrics": {
            "model_mae": report["results"]["model"]["overall"]["mae"],
            "model_rmse": report["results"]["model"]["overall"]["rmse"],
            "model_smape": report["results"]["model"]["overall"]["smape"],
            "seasonal_naive_mae": report["results"]["seasonal_naive"]["overall"]["mae"],
            "station_median_mae": report["results"]["station_median"]["overall"]["mae"],
        },
        "protocol": {
            "embargo_days": report["fold_plan"]["embargo_days"],
            "n_folds": len(report["fold_plan"]["folds"]),
            "skipped_months": report["fold_plan"]["skipped_months"],
        },
        "artifact": {
            "path": ARTIFACT_NAME,
            "sha256": sha256_file(artifact_path),
            "size_bytes": Path(artifact_path).stat().st_size,
        },
    }


def step_publish(
    release_dir: Path,
    features_dir: Path,
    report: dict,
    artifact_path: Path,
    model_release_id: str,
    registry_info: dict,
    *,
    releases_dir: Path = DEFAULT_RELEASES_DIR,
) -> dict:
    """Write (or confirm) the committed release manifest; a different manifest
    under the same release ID is a collision and fails."""
    releases_dir = Path(releases_dir)
    manifest = build_release_manifest(
        release_dir, features_dir, report, artifact_path, model_release_id, registry_info
    )
    path = releases_dir / model_release_id / "manifest.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing == manifest:
            return {"created": False, "manifest": manifest, "path": path}
        raise RuntimeError(
            f"release ID collision: {path} exists with different content; "
            "cut a new release ID instead of overwriting an immutable release"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"created": True, "manifest": manifest, "path": path}


# -- promotion and rollback ------------------------------------------------------


def read_pin(releases_dir: Path) -> dict | None:
    path = Path(releases_dir) / "pinned.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def pin_model(
    model_release_id: str,
    *,
    releases_dir: Path = DEFAULT_RELEASES_DIR,
    tracking_uri: str = DEFAULT_TRACKING_URI,
) -> dict:
    """Promote a candidate to pinned through the gate: strictly better pooled
    protocol MAE than the pinned release (the first pin must beat both
    committed baselines). Refusals leave the pin untouched and raise."""
    releases_dir = Path(releases_dir)
    manifest_path = releases_dir / model_release_id / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"no release manifest for {model_release_id}: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    client = _client(tracking_uri)
    previous = read_pin(releases_dir)
    if previous is not None and previous["model_release_id"] == model_release_id:
        return {"pinned": model_release_id, "previous": None, "changed": False}

    version = find_registry_version(client, model_release_id)
    stage = version.tags.get("release_stage") if version is not None else None
    is_rollback = stage == RELEASE_STAGE_REGISTERED  # a demoted former pin

    prev_manifest = None
    if previous is not None:
        prev_path = releases_dir / previous["model_release_id"] / "manifest.json"
        prev_manifest = json.loads(prev_path.read_text(encoding="utf-8"))

    if not is_rollback:
        if previous is not None:
            gate_mae = prev_manifest["metrics"]["model_mae"]
            gate_source = f"pinned release {previous['model_release_id']}"
        else:
            gate_mae = min(
                manifest["metrics"]["seasonal_naive_mae"],
                manifest["metrics"]["station_median_mae"],
            )
            gate_source = "committed M03 baselines"
        if not manifest["metrics"]["model_mae"] < gate_mae:
            raise ValueError(
                f"promotion refused: {model_release_id} MAE {manifest['metrics']['model_mae']} "
                f"is not better than {gate_source} MAE {gate_mae}; the pin stays"
            )

    if prev_manifest is not None:
        client.set_model_version_tag(
            REGISTRY_MODEL_NAME,
            prev_manifest["mlflow_model_version"],
            "release_stage",
            RELEASE_STAGE_REGISTERED,
        )
    client.set_model_version_tag(
        REGISTRY_MODEL_NAME, manifest["mlflow_model_version"], "release_stage", RELEASE_STAGE_PINNED
    )
    pin = {"model_release_id": model_release_id, "manifest_sha256": sha256_file(manifest_path)}
    pin_path = releases_dir / "pinned.json"
    pin_path.write_text(json.dumps(pin, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "pinned": model_release_id,
        "previous": previous["model_release_id"] if previous else None,
        "changed": True,
        "rollback": is_rollback,
    }


def verify_pin(
    release_dir: Path,
    cfg: dict,
    features_dir: Path,
    *,
    releases_dir: Path = DEFAULT_RELEASES_DIR,
    models_dir: Path = DEFAULT_MODELS_DIR,
    issue_date: date | None = None,
    out_dir: Path | None = None,
) -> dict:
    """Rollback verification: the pinned artifact must match its manifest
    checksum, and scoring a fixed verification day must produce deterministic
    prediction bytes. Returns the summary recorded by the drill."""
    releases_dir, models_dir = Path(releases_dir), Path(models_dir)
    pin = read_pin(releases_dir)
    if pin is None:
        raise RuntimeError("no pinned release: write releases/models/pinned.json first")
    manifest_path = releases_dir / pin["model_release_id"] / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if sha256_file(manifest_path) != pin["manifest_sha256"]:
        raise RuntimeError("pinned manifest changed since the pin was written")

    artifact_path = models_dir / pin["model_release_id"] / ARTIFACT_NAME
    if sha256_file(artifact_path) != manifest["artifact"]["sha256"]:
        raise RuntimeError("pinned artifact does not match its manifest checksum")
    pipe = joblib.load(artifact_path)

    fmanifest = json.loads((Path(features_dir) / "manifest.json").read_text(encoding="utf-8"))
    day = issue_date or date.fromisoformat(fmanifest["issue_end"])
    demand = load_demand(release_dir, cfg)
    table = load_training_features(features_dir, day, day)
    data = build_training_data(table, demand, [day])
    preds = pipe.predict(data.X)
    grid = np.full((len(data.stations), TARGET_HOURS), np.nan)
    grid[data.station_idx, data.hour_idx] = preds
    predictions = {
        station: [_round(v) for v in row] for station, row in zip(data.stations, grid, strict=True)
    }
    payload = (
        json.dumps(
            {
                "model_release_id": pin["model_release_id"],
                "issue_day": day.isoformat(),
                "predictions": predictions,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    predictions_sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"verify-{pin['model_release_id']}-{day.isoformat()}.json").write_text(
            payload, encoding="utf-8"
        )
    return {
        "model_release_id": pin["model_release_id"],
        "manifest_sha256": pin["manifest_sha256"],
        "artifact_sha256": manifest["artifact"]["sha256"],
        "issue_day": day.isoformat(),
        "rows": int(preds.size),
        "predictions_sha256": predictions_sha,
    }


# -- the full pipeline ----------------------------------------------------------


def run_pipeline(
    release_dir: Path,
    cfg: dict,
    features_dir: Path,
    out_dir: Path,
    model_release_id: str = DEFAULT_MODEL_RELEASE_ID,
    *,
    releases_dir: Path = DEFAULT_RELEASES_DIR,
    models_dir: Path = DEFAULT_MODELS_DIR,
    tracking_uri: str = DEFAULT_TRACKING_URI,
    max_iter: int = MAX_ITER,
    seed: int = RANDOM_SEED,
    grid: dict[str, list] | None = None,
    sel_train_end: date = SEL_TRAIN_END,
    sel_val_start: date = SEL_VAL_START,
    sel_val_end: date = SEL_VAL_END,
) -> dict:
    """validate → features → train → evaluate → register → publish, each step
    skipped when its existing output already matches the current inputs."""
    release_dir, features_dir, out_dir = Path(release_dir), Path(features_dir), Path(out_dir)
    summary: dict = {"model_release_id": model_release_id}
    summary["validate"] = step_validate(release_dir, cfg)
    summary["features"] = step_features(release_dir, cfg, features_dir)
    report, artifact_path, reused = step_train(
        release_dir,
        cfg,
        features_dir,
        out_dir,
        model_release_id,
        models_dir,
        tracking_uri=tracking_uri,
        max_iter=max_iter,
        seed=seed,
        grid=grid,
        sel_train_end=sel_train_end,
        sel_val_start=sel_val_start,
        sel_val_end=sel_val_end,
    )
    summary["train"] = {"reused": reused, "model_mae": report["acceptance"]["model_mae"]}
    summary["evaluate"] = step_evaluate(report)
    summary["register"] = step_register(
        release_dir,
        features_dir,
        report,
        artifact_path,
        model_release_id,
        tracking_uri=tracking_uri,
    )
    summary["publish"] = step_publish(
        release_dir,
        features_dir,
        report,
        artifact_path,
        model_release_id,
        summary["register"],
        releases_dir=releases_dir,
    )
    return summary
