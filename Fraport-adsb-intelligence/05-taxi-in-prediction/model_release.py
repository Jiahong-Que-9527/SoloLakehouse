"""Verify the container replay and register the frozen Fraport candidate locally."""

import argparse
import fcntl
import hashlib
import json
import pickle
import re
import shutil
import tempfile
from pathlib import Path

from median_baseline import sha256

MODEL_NAME = "fraport-taxi-in"
REPLAY_ARTIFACTS = {
    "model": ("candidate", "model.pkl"),
    "candidate": ("candidate", "candidate-report.json"),
    "evaluation": ("evaluation", "evaluation-report.json"),
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_bytes())


def json_text(value: dict) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def reference_hashes(candidate: Path, evaluation: Path) -> dict:
    directories = {"candidate": candidate, "evaluation": evaluation}
    return {role: sha256(directories[directory] / filename)
            for role, (directory, filename) in REPLAY_ARTIFACTS.items()}


def validate_image(image: str, commit: str) -> None:
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("an image SHA-256 and a full source commit are required")


def verify_replay(candidate: Path, evaluation: Path, replay: Path, image: str, commit: str) -> dict:
    validate_image(image, commit)
    expected = reference_hashes(candidate, evaluation)
    actual = reference_hashes(replay / "candidate", replay / "evaluation")
    if actual != expected:
        mismatches = sorted(role for role in expected if actual[role] != expected[role])
        raise ValueError(f"container replay differs from the pinned reference: {', '.join(mismatches)}")
    return {"status": "verified", "image_id": image, "source_commit": commit, "sha256": actual}


def release_payload(candidate_dir: Path, evaluation_dir: Path, evidence: dict) -> dict:
    validate_image(evidence["image_id"], evidence["source_commit"])
    hashes = reference_hashes(candidate_dir, evaluation_dir)
    if evidence["status"] != "verified" or evidence["sha256"] != hashes:
        raise ValueError("container evidence is missing or pinned to different artifacts")
    candidate = read_json(candidate_dir / "candidate-report.json")
    evaluation = read_json(evaluation_dir / "evaluation-report.json")
    if (candidate["model_sha256"] != hashes["model"] or evaluation["model_sha256"] != hashes["model"]
            or candidate["candidate_id"] != evaluation["candidate_id"]
            or candidate["baseline_id"] != evaluation["baseline_id"]
            or candidate["baseline_report_sha256"] != evaluation["baseline_report_sha256"]
            or candidate["feature_manifest_sha256"] != evaluation["training_manifest_sha256"]):
        raise ValueError("candidate and frozen evaluation provenance do not match")
    if not (candidate["mae_improvement_seconds"] > 0 and evaluation["mae_improvement_seconds"] > 0):
        raise ValueError("the candidate must beat the frozen median on both evaluation windows")
    return {
        "schema_version": "fraport-model-release-v1", "stage": "candidate",
        "source_commit": evidence["source_commit"], "container_image_id": evidence["image_id"],
        "candidate_id": candidate["candidate_id"], "baseline_id": candidate["baseline_id"],
        "feature_columns": candidate["feature_columns"], "availability": evaluation["availability"],
        "training_release_id": candidate["label_release_id"],
        "training_dataset_id": candidate["feature_dataset_id"],
        "training_manifest_sha256": candidate["feature_manifest_sha256"],
        "evaluation_release_id": evaluation["evaluation_label_release_id"],
        "evaluation_dataset_id": evaluation["evaluation_dataset_id"],
        "evaluation_manifest_sha256": evaluation["evaluation_manifest_sha256"],
        "baseline_report_sha256": candidate["baseline_report_sha256"],
        "candidate_report_sha256": hashes["candidate"], "evaluation_report_sha256": hashes["evaluation"],
        "november_holdout_metrics_seconds": candidate["holdout_metrics_seconds"],
        "december_frozen_metrics_seconds": evaluation["candidate_metrics_seconds"],
        "december_frozen_baseline_metrics_seconds": evaluation["baseline_metrics_seconds"],
        "artifact": {"path": "model.pkl", "sha256": hashes["model"]},
    }


def register_version(client, payload: dict, bundle: dict, tracking_dir: Path):
    import mlflow
    from mlflow.exceptions import MlflowException
    from mlflow.models import ModelSignature
    from mlflow.types import ColSpec, Schema

    release_id = payload["model_release_id"]
    try:
        client.get_registered_model(MODEL_NAME)
    except MlflowException as exc:
        if exc.error_code != "RESOURCE_DOES_NOT_EXIST":
            raise
        client.create_registered_model(MODEL_NAME)
    versions = client.search_model_versions(f"name='{MODEL_NAME}' and tags.model_release_id='{release_id}'")
    if len(versions) > 1:
        raise ValueError("the model release ID already has multiple registry versions")
    if versions:
        version = versions[0]
        if version.tags.get("candidate_sha256") != payload["artifact"]["sha256"]:
            raise ValueError("registry version has a different candidate checksum")
        return version
    experiment = client.get_experiment_by_name(MODEL_NAME)
    experiment_id = (experiment.experiment_id if experiment else client.create_experiment(
        MODEL_NAME, artifact_location=(tracking_dir / "artifacts").as_uri()))
    signature = ModelSignature(inputs=Schema([ColSpec("double", feature) for feature in bundle["feature_columns"]]))
    with mlflow.start_run(experiment_id=experiment_id, run_name=f"release-{release_id}") as run:
        info = mlflow.sklearn.log_model(
            bundle["estimator"], name="model", signature=signature,
            serialization_format="skops",
            skops_trusted_types=["sklearn.ensemble._hist_gradient_boosting.predictor.TreePredictor"],
            pip_requirements=["mlflow==3.18.0", "scikit-learn==1.9.1", "numpy==2.5.5", "skops==0.16.0"],
        )
        return client.create_model_version(MODEL_NAME, info.model_uri, run_id=run.info.run_id, tags={
            "model_release_id": release_id, "candidate_sha256": payload["artifact"]["sha256"],
            "release_stage": payload["stage"], "source_commit": payload["source_commit"],
        })


def register_release(candidate: Path, evaluation: Path, evidence_path: Path, output: Path, tracking_dir: Path) -> dict:
    import mlflow
    import numpy as np
    import pandas as pd

    evidence = read_json(evidence_path)
    payload = release_payload(candidate, evaluation, evidence)
    key = hashlib.sha256(json_text(payload).encode()).hexdigest()[:16]
    payload["model_release_id"] = f"fraport-taxi-in-{key}"
    tracking_dir = tracking_dir.resolve()
    tracking_dir.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(f"sqlite:///{tracking_dir / 'tracking.db'}")
    # The evidence pins a model generated by the local training command.
    with (candidate / "model.pkl").open("rb") as stream:
        bundle = pickle.load(stream)
    if bundle["feature_columns"] != payload["feature_columns"]:
        raise ValueError("artifact feature order differs from the candidate report")
    if output.exists():
        existing = read_json(output / "manifest.json")
        if (any(existing[key] != value for key, value in payload.items())
                or sha256(output / "model.pkl") != payload["artifact"]["sha256"]):
            raise ValueError("output contains a different release or a changed model")
    client = mlflow.MlflowClient()
    with (tracking_dir / ".model-release.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        version = register_version(client, payload, bundle, tracking_dir)
        uri = f"models:/{MODEL_NAME}/{version.version}"
        loaded = mlflow.pyfunc.load_model(uri)
        sample = pd.DataFrame([[0.0] * len(bundle["feature_columns"])], columns=bundle["feature_columns"])
        np.testing.assert_array_equal(loaded.predict(sample), bundle["estimator"].predict(sample.to_numpy()))
        manifest = {**payload, "registry": {"model_name": MODEL_NAME, "version": int(version.version),
                                            "source_run_id": version.run_id, "model_uri": uri}}
        if output.exists():
            if read_json(output / "manifest.json") != manifest:
                raise ValueError("existing manifest does not match the registered model version")
            return manifest
        output.parent.mkdir(parents=True, exist_ok=True)
        staged = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
        try:
            shutil.copyfile(candidate / "model.pkl", staged / "model.pkl")
            (staged / "manifest.json").write_text(json_text(manifest))
            staged.rename(output)
        finally:
            if staged.exists():
                shutil.rmtree(staged)
        return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser("verify-container")
    verify.add_argument("--replay", type=Path, required=True)
    verify.add_argument("--image-id", required=True)
    verify.add_argument("--source-commit", required=True)
    register = commands.add_parser("register")
    register.add_argument("--container-evidence", type=Path, required=True)
    register.add_argument("--tracking-dir", type=Path, required=True)
    for command in (verify, register):
        command.add_argument("--candidate", type=Path, required=True)
        command.add_argument("--evaluation", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "verify-container":
            result = verify_replay(args.candidate, args.evaluation, args.replay, args.image_id, args.source_commit)
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(json_text(result))
        else:
            result = register_release(args.candidate, args.evaluation, args.container_evidence,
                                      args.output, args.tracking_dir)
    except (KeyError, ValueError, OSError) as exc:
        parser.exit(1, f"model release: {exc}\n")
    print(json_text(result), end="")


if __name__ == "__main__":
    main()
