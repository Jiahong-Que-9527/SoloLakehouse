"""Deploy a pinned EDDF image after the measured input audit is available."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

from cloud_acceptance import HERE, gcloud, verify

SERVICE = "eddf-taxi-in"
REGION = "europe-west3"


def measured_audit(path: Path) -> str:
    raw = path.read_bytes()
    audit = json.loads(raw)
    if (audit.get("schema_version") != "frankfurt-airport-availability-audit-v1" or audit.get("status") != "measured"
            or not audit.get("observed_partitions") or audit.get("arrival_triggers", {}).get("observed", 0) <= 0
            or audit.get("observation_delays", {}).get("invalid_timestamps_including_context") != 0):
        raise ValueError("deployment requires the measured EDDF availability audit")
    return hashlib.sha256(raw).hexdigest()


def deployment_args(args) -> list[str]:
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", args.project):
        raise ValueError("expected a Google Cloud project ID")
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,62}", args.repository):
        raise ValueError("expected a private Artifact Registry repository name")
    prefix = f"{REGION}-docker.pkg.dev/{args.project}/{args.repository}/{SERVICE}@sha256:"
    if not args.image.startswith(prefix) or not re.fullmatch(r"[a-f0-9]{64}", args.image.removeprefix(prefix)):
        raise ValueError("image must be pinned by digest in the configured Frankfurt Airport repository")
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,30}", args.suffix):
        raise ValueError("invalid revision suffix")
    for account in (args.runtime, args.invoker):
        if not re.fullmatch(r"[a-z][a-z0-9-]+@" + re.escape(args.project) + r"\.iam\.gserviceaccount\.com", account):
            raise ValueError("expected a runtime and invoker service account in the project")
    command = ["run", "deploy", SERVICE, "--project", args.project, "--region", REGION, "--image", args.image,
               "--service-account", args.runtime, "--revision-suffix", args.suffix, "--no-allow-unauthenticated",
               "--invoker-iam-check", "--port=8080", "--cpu=1", "--memory=1Gi", "--concurrency=4",
               "--min-instances=0", "--max-instances=1", "--quiet",
               "--startup-probe=httpGet.path=/health,httpGet.port=8080,periodSeconds=5,timeoutSeconds=3,failureThreshold=12"]
    if args.mode == "candidate":
        command.extend(["--no-traffic", "--tag=candidate"])
    return command


def deploy(args) -> dict:
    audit_sha256 = measured_audit(args.audit)
    command = deployment_args(args)
    json.loads(args.evidence.read_bytes())["probe"]["model"]
    services = gcloud("run", "services", "list", "--project", args.project, "--region", REGION,
                      "--format=value(metadata.name)").splitlines()
    if (SERVICE in services) != (args.mode == "candidate"):
        raise ValueError("deployment mode does not match whether the service already exists")
    gcloud(*command, timeout=300)
    result = verify(SimpleNamespace(project=args.project, region=REGION, service=SERVICE,
                                    revision=f"{SERVICE}-{args.suffix}", image=args.image, invoker=args.invoker,
                                    tag="candidate" if args.mode == "candidate" else None, evidence=args.evidence))
    return result | {"availability_audit_sha256": audit_sha256}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("project", "repository", "image", "suffix", "runtime", "invoker"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--mode", choices=("initial", "candidate"), required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, default=HERE / "evidence/cloud-run-image-rehearsal.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError("choose a new output file")
        report = deploy(args)
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2, sort_keys=True)
            output.write("\n")
    except (KeyError, OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"Cloud Run deploy: {exc}\n")


if __name__ == "__main__":
    main()
