"""Cache the phase 04 feature builds and the pinned phase 05 Docker replay."""

import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import date, timedelta
from pathlib import Path, PurePosixPath
from uuid import uuid4

FRANKFURT_AIRPORT = Path(__file__).resolve().parent.parent
FEATURE_CODE = FRANKFURT_AIRPORT / "04-aviation-lakehouse"
MODEL_RELEASE = FRANKFURT_AIRPORT / "05-taxi-in-prediction/releases/frankfurt-airport-taxi-in-ca2c8f9b21863f18.json"
VALIDATION_FROM = "2024-11-16"
REPLAY_FILES = {"candidate/model.pkl": ("artifact", "sha256"),
                "candidate/candidate-report.json": ("candidate_report_sha256",),
                "evaluation/evaluation-report.json": ("evaluation_report_sha256",)}


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def identity(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def feature_plan(silver: Path, state: Path, handoff: dict) -> tuple[Path, dict]:
    month = handoff["month_utc"]
    start = date.fromisoformat(month + "-01")
    end = (start + timedelta(days=32)).replace(day=1)
    observations = []
    for offset in range(-1, (end - start).days):
        day = (start + timedelta(days=offset)).isoformat()
        manifest = silver / day / "run_manifest.json"
        raw = manifest.read_bytes()
        payload = json.loads(raw)["outputs"]["observations.parquet"]
        observations.append({"day_utc": day, "sha256": payload["sha256"],
                             "manifest_sha256": hashlib.sha256(raw).hexdigest()})
    pins = {"label_manifest_sha256": handoff["manifest_sha256"], "silver_observations": observations,
            "availability": {"mode": "simulated_fixed_delay", "delay_seconds": 5},
            "code_sha256": {name: digest(FEATURE_CODE / name) for name in (
                "feature_replay.py", "feature_replay.sql", "release_inputs.py", "uv.lock")}}
    return state / "features" / f"{month}-{identity(pins)}", pins


def checked_features(directory: Path, pins: dict) -> dict:
    path = directory / "manifest.json"
    raw = path.read_bytes()
    manifest = json.loads(raw)
    if (manifest["label_release"]["manifest_sha256"] != pins["label_manifest_sha256"]
            or any(manifest[key] != pins[key] for key in ("silver_observations", "availability", "code_sha256"))
            or digest(directory / "training.parquet") != manifest["files"]["training.parquet"]["sha256"]):
        raise ValueError("feature artifact differs from its input pins or payload checksum")
    return {"feature_dataset_id": manifest["feature_dataset_id"], "manifest_sha256": hashlib.sha256(raw).hexdigest(),
            "predictions": manifest["predictions"], "directory": str(directory)}


def features_for(silver: Path, state: Path, release: Path, handoff: dict, *, build: bool) -> dict:
    output, pins = feature_plan(silver, state, handoff)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        reused = output.is_dir()
        if not reused:
            if not build:
                raise ValueError(f"build the {handoff['month_utc']} features before training")
            with tempfile.TemporaryDirectory(dir=output.parent) as scratch:
                staged = Path(scratch) / "dataset"
                subprocess.run([sys.executable, str(FEATURE_CODE / "feature_replay.py"), "--silver-root", str(silver),
                                "--label-release", str(release), "--output", str(staged),
                                "--simulated-delay-seconds", "5"], check=True, stdout=sys.stderr)
                checked_features(staged, pins)
                staged.rename(output)
        return checked_features(output, pins) | {"reused": reused}


def docker_replay(docker: str, image: str, training: Path, evaluation: Path, baseline: Path, output: Path) -> None:
    container = f"frankfurt-airport-dagster-{uuid4().hex}"
    def call(*arguments, **kwargs):
        return subprocess.run([docker, *arguments], check=True, **kwargs)

    call("create", "--pull=never", "--network", "none", "--name", container, image, "/bin/sh", "/app/container_replay.sh",
         "/input/training", "/input/evaluation", "/input/baseline.json", VALIDATION_FROM, "/output", stdout=sys.stderr)
    try:
        with tempfile.TemporaryFile() as bundle:
            with tarfile.open(fileobj=bundle, mode="w") as tar:
                for directory, name in ((training, "training"), (evaluation, "evaluation")):
                    folder = tarfile.TarInfo(name)
                    folder.type, folder.mode = tarfile.DIRTYPE, 0o755
                    tar.addfile(folder)
                    for file in ("manifest.json", "training.parquet"):
                        tar.add(directory / file, arcname=f"{name}/{file}", filter=readable_file)
                tar.add(baseline, arcname="baseline.json", filter=readable_file)
            bundle.seek(0)
            call("cp", "-", f"{container}:/input", stdin=bundle, stdout=sys.stderr)
        call("start", "-a", container, stdout=sys.stderr)
        exit_code = call("inspect", "--format", "{{.State.ExitCode}}", container, capture_output=True, text=True)
        if exit_code.stdout.strip() != "0":
            raise ValueError("the pinned training container did not exit successfully")
        with tempfile.TemporaryFile() as bundle:
            call("cp", f"{container}:/output/.", "-", stdout=bundle)
            bundle.seek(0)
            with tarfile.open(fileobj=bundle) as tar:
                for member in tar:
                    name = str(PurePosixPath(member.name))
                    if member.isfile() and name in REPLAY_FILES:
                        destination = output / name
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        with tar.extractfile(member) as source, destination.open("xb") as target:
                            shutil.copyfileobj(source, target)
    finally:
        call("rm", "-f", container, stdout=sys.stderr)


def readable_file(member: tarfile.TarInfo) -> tarfile.TarInfo:
    if not member.isfile():
        raise ValueError("expected a regular container input file")
    member.mode = 0o644
    return member


def checked_replay(output: Path, release: dict) -> dict:
    hashes = {}
    for name, keys in REPLAY_FILES.items():
        expected = release
        for key in keys:
            expected = expected[key]
        hashes[name] = digest(output / name)
        if hashes[name] != expected:
            raise ValueError(f"container replay differs from the M4 release: {name}")
    return hashes


def replay_model(state: Path, training: dict, evaluation: dict, baseline: Path, docker: str) -> dict:
    raw = MODEL_RELEASE.read_bytes()
    release = json.loads(raw)
    for role, feature in (("training", training), ("evaluation", evaluation)):
        if (feature["feature_dataset_id"] != release[f"{role}_dataset_id"]
                or feature["manifest_sha256"] != release[f"{role}_manifest_sha256"]):
            raise ValueError(f"{role} features do not match the pinned M4 model release")
    baseline_hash = digest(baseline)
    if baseline_hash != release["baseline_report_sha256"]:
        raise ValueError("baseline report does not match the pinned M4 model release")
    inputs = {"training_manifest_sha256": training["manifest_sha256"],
              "evaluation_manifest_sha256": evaluation["manifest_sha256"], "baseline_sha256": baseline_hash,
              "model_release_sha256": hashlib.sha256(raw).hexdigest(), "image_id": release["container_image_id"],
              "validation_from": VALIDATION_FROM}
    output = state / "training" / identity(inputs)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        reused = output.is_dir()
        if not reused:
            with tempfile.TemporaryDirectory(dir=output.parent) as scratch:
                staged = Path(scratch) / "replay"
                staged.mkdir()
                docker_replay(docker, inputs["image_id"], Path(training["directory"]), Path(evaluation["directory"]), baseline, staged)
                checked_replay(staged, release)
                staged.rename(output)
        return {"model_release_id": release["model_release_id"], **inputs, "artifacts": checked_replay(output, release),
                "directory": str(output), "reused": reused}
