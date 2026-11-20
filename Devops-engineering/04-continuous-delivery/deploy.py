#!/usr/bin/env python3
"""Local release deployer for the Energy Data Quality Service (D04).

Subcommands:
  deploy <manifest.json>   validate, deploy, verify; roll back on failure
  recover <manifest.json>  finish verification after an interrupted deploy,
                           or restore the last verified manifest
  rollback                 restore the last verified manifest
  status                   print the current deployment state

State and history live under releases/ (state.json, history.jsonl).
Requires docker, docker compose and the reference-service compose stack.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RELEASES = ROOT / "releases"
STATE = RELEASES / "state.json"
HISTORY = RELEASES / "history.jsonl"
COMPOSE_DIR = ROOT.parent / "reference-service" / "compose"
FIXTURES = ROOT.parent / "reference-service" / "fixtures"

DIGEST_RE = re.compile(r"^sha256:[a-f0-9]{64}$")
REQUIRED_FIELDS = (
    "release_id",
    "source_sha",
    "image",
    "digest",
    "config_revision",
    "config",
    "created_at",
)
REQUIRED_CONFIG = ("audit_report_file", "fixture_sha256", "port")
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
TIMEOUT_S = int(os.environ.get("DEPLOY_TIMEOUT_S", "90"))


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(
    cmd: list[str],
    cwd: Path | None = None,
    env: dict | None = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=env)


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"status": "empty", "requested": None, "last_verified": None}


def save_state(state: dict) -> None:
    RELEASES.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2) + "\n")


def append_history(record: dict) -> None:
    RELEASES.mkdir(parents=True, exist_ok=True)
    with HISTORY.open("a") as handle:
        handle.write(json.dumps(record) + "\n")


def http_get(url: str, timeout: int = 5):
    try:
        with OPENER.open(url, timeout=timeout) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except Exception:
        return 0, None


def validate_manifest(path: str) -> dict:
    manifest = json.loads(Path(path).read_text())
    for field in REQUIRED_FIELDS:
        if field not in manifest:
            raise ValueError(f"missing field: {field}")
    if not DIGEST_RE.match(manifest["digest"]):
        raise ValueError("digest must be sha256:<64 hex characters>")
    config = manifest["config"]
    for field in REQUIRED_CONFIG:
        if field not in config:
            raise ValueError(f"missing config field: {field}")
    fixture = FIXTURES / config["audit_report_file"]
    actual = hashlib.sha256(fixture.read_bytes()).hexdigest()
    if actual != config["fixture_sha256"]:
        raise ValueError(
            f"fixture checksum mismatch for {config['audit_report_file']}"
        )
    return manifest


def compose_env(manifest: dict) -> dict:
    return {
        **os.environ,
        "ENERGY_QUALITY_IMAGE": f"{manifest['image']}@{manifest['digest']}",
        "AUDIT_REPORT_FILE": manifest["config"]["audit_report_file"],
        "ENERGY_QUALITY_PORT": str(manifest["config"]["port"]),
    }


def compose_up(manifest: dict) -> bool:
    result = run(
        ["docker", "compose", "up", "-d", "--quiet-pull", "--force-recreate"],
        cwd=COMPOSE_DIR,
        env=compose_env(manifest),
    )
    return result.returncode == 0


def compose_down() -> None:
    run(["docker", "compose", "down"], cwd=COMPOSE_DIR)


def container_id() -> str:
    result = run(
        ["docker", "compose", "ps", "-q", "energy-quality"], cwd=COMPOSE_DIR
    )
    return result.stdout.strip()


def container_image() -> str | None:
    cid = container_id()
    if not cid:
        return None
    result = run(["docker", "inspect", "--format", "{{.Image}}", cid])
    return result.stdout.strip() or None


def manifest_image_id(manifest: dict) -> str | None:
    result = run(
        [
            "docker", "image", "inspect", "--format", "{{.Id}}",
            f"{manifest['image']}@{manifest['digest']}",
        ]
    )
    return result.stdout.strip() or None


def wait_ready(port: int, timeout: int):
    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{port}/v1/quality/latest"
    while time.time() < deadline:
        code, body = http_get(url)
        if code == 200:
            return True, body
        time.sleep(2)
    return False, None


def verify(manifest: dict) -> tuple[bool, str]:
    ok, body = wait_ready(int(manifest["config"]["port"]), TIMEOUT_S)
    if not ok:
        return False, "readiness not reached within timeout"
    expected = manifest["config"].get("expected_report_id")
    if expected is not None and body.get("report_id") != expected:
        return False, f"report identity mismatch: {body.get('report_id')}"
    return True, "verified"


def record_outcome(
    action: str,
    manifest: dict | None,
    outcome: str,
    started: float,
    note: str,
) -> None:
    append_history(
        {
            "time": now(),
            "action": action,
            "release_id": manifest["release_id"] if manifest else None,
            "requested_digest": manifest["digest"] if manifest else None,
            "outcome": outcome,
            "duration_s": round(time.time() - started),
            "note": note,
        }
    )


def deploy_manifest(manifest: dict, action: str, started: float) -> bool:
    image_id = manifest_image_id(manifest)
    if not compose_up(manifest):
        record_outcome(action, manifest, "compose_up_failed", started, "")
        return False
    observed = container_image()
    identity_ok = image_id is not None and observed == image_id
    ok, note = verify(manifest)
    if ok and identity_ok:
        state = load_state()
        state.update(
            {
                "status": "verified",
                "verified_at": now(),
                "requested": None,
                "last_verified": {**manifest, "verified_at": now()},
            }
        )
        save_state(state)
        record_outcome(
            action, manifest, "verified", started,
            f"identity_match={identity_ok}",
        )
        return True
    record_outcome(action, manifest, "verification_failed", started, note)
    return False


def rollback(started: float, reason: str) -> bool:
    state = load_state()
    previous = state.get("last_verified")
    if not previous:
        compose_down()
        save_state({"status": "empty", "requested": None, "last_verified": None})
        record_outcome("rollback", None, "rolled_back_to_empty", started, reason)
        return True
    ok = deploy_manifest(previous, "rollback", started)
    if not ok:
        state = load_state()
        state["status"] = "rollback_failed"
        save_state(state)
        record_outcome(
            "rollback", previous, "rollback_failed", started,
            "manual recovery required: redeploy the last verified manifest",
        )
    return ok


def cmd_deploy(path: str) -> int:
    started = time.time()
    try:
        manifest = validate_manifest(path)
    except Exception as exc:  # noqa: BLE001 - reject with the reason
        record_outcome("deploy", None, "rejected", started, str(exc))
        print(f"REJECTED before deployment: {exc}")
        return 1
    state = load_state()
    if state.get("status") == "deploying":
        print(
            "OVERLAP: a deploy is already in progress. "
            f"Run: deploy.py recover {path}"
        )
        return 2
    pull = run(["docker", "pull", f"{manifest['image']}@{manifest['digest']}"])
    if pull.returncode != 0:
        record_outcome("deploy", manifest, "pull_failed", started, "")
        print("ERROR: image pull failed")
        return 1
    state = {
        "status": "deploying",
        "status_since": now(),
        "requested": manifest,
        "last_verified": state.get("last_verified"),
        "attempt_started": now(),
    }
    save_state(state)
    if deploy_manifest(manifest, "deploy", started):
        print(f"VERIFIED: {manifest['release_id']} is live")
        return 0
    print(f"FAILED: {manifest['release_id']} did not verify; rolling back")
    if rollback(started, f"deployment of {manifest['release_id']} failed"):
        print("ROLLED BACK to the last verified manifest")
        return 3
    print("ROLLBACK FAILED - manual recovery required (see history.jsonl)")
    return 4


def cmd_recover(path: str) -> int:
    started = time.time()
    state = load_state()
    if state.get("status") != "deploying":
        print("Nothing to recover: state is not 'deploying'.")
        return 1
    try:
        manifest = validate_manifest(path)
    except Exception as exc:  # noqa: BLE001
        print(f"Invalid manifest for recovery: {exc}")
        return 1
    requested = state.get("requested") or {}
    if requested.get("release_id") != manifest["release_id"]:
        print(
            "Requested release differs from the interrupted one; "
            "restoring the last verified manifest."
        )
        return 0 if rollback(started, "interrupted deploy of another release") else 4
    observed = container_image()
    expected = manifest_image_id(manifest)
    if observed and observed == expected:
        ok, note = verify(manifest)
        if ok:
            state.update(
                {
                    "status": "verified",
                    "verified_at": now(),
                    "requested": None,
                    "last_verified": {**manifest, "verified_at": now()},
                }
            )
            save_state(state)
            record_outcome(
                "recover", manifest, "verified", started,
                "observed runtime matched the requested revision",
            )
            print(f"RECOVERY COMPLETE: {manifest['release_id']} verified")
            return 0
        record_outcome("recover", manifest, "verification_failed", started, note)
    else:
        record_outcome(
            "recover", manifest, "identity_mismatch", started,
            "running container does not match the requested revision",
        )
    return 0 if rollback(started, "recovery could not verify the release") else 4


def cmd_rollback() -> int:
    return 0 if rollback(time.time(), "manual rollback requested") else 4


def cmd_status() -> int:
    print(json.dumps(load_state(), indent=2))
    if HISTORY.exists():
        lines = HISTORY.read_text().strip().splitlines()
        print("\nLast history entries:")
        for line in lines[-3:]:
            print(" ", line)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("deploy", "recover"):
        sub.add_parser(name).add_argument("manifest")
    sub.add_parser("rollback")
    sub.add_parser("status")
    args = parser.parse_args()
    if args.command == "deploy":
        return cmd_deploy(args.manifest)
    if args.command == "recover":
        return cmd_recover(args.manifest)
    if args.command == "rollback":
        return cmd_rollback()
    return cmd_status()


if __name__ == "__main__":
    sys.exit(main())
