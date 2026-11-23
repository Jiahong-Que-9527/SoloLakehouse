"""Verify an existing private Cloud Run revision and its serving telemetry."""

import argparse
import http.client
import json
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
PROBE = {"airport_icao": "EDDF", "prediction_at": "2025-04-15T15:30:05+02:00", "features": {
    "approach_speed_mps": 70, "approach_altitude_m": 150, "approach_vertical_rate_mps": -2,
    "approach_distance_m": 1200, "ground_speed_mps": 35, "approach_age_s": 9,
}}


def gcloud(*args: str, timeout: int = 45) -> str:
    result = subprocess.run(["gcloud", *args], text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def service_url(url: str) -> str:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".run.app")
            or parsed.netloc != parsed.hostname or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise ValueError("expected a direct HTTPS Cloud Run service URL")
    return f"https://{parsed.hostname}"


def target_url(status: dict, revision: str, tag: str | None) -> tuple[str, str]:
    base = service_url(status["url"])
    traffic = status["traffic"]
    if tag is not None:
        targets = [item for item in traffic if item.get("tag") == tag]
        if (len(targets) != 1 or targets[0].get("revisionName") != revision
                or int(targets[0].get("percent", 0)) != 0
                or any(item.get("revisionName") == revision and int(item.get("percent", 0)) for item in traffic)):
            raise ValueError("the tagged candidate must have zero service traffic")
        return base, service_url(targets[0]["url"])
    active = [item for item in traffic if int(item.get("percent", 0)) > 0]
    if len(active) != 1 or active[0].get("revisionName") != revision or int(active[0]["percent"]) != 100:
        raise ValueError("the expected revision does not have 100% of service traffic")
    return base, base


def request(url: str, route: str, token: str | None = None, body: dict | None = None) -> tuple[int, str | None, str]:
    connection = http.client.HTTPSConnection(urlsplit(service_url(url)).hostname, timeout=15)
    headers = {} if token is None else {"Authorization": f"Bearer {token}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    try:
        connection.request("GET" if body is None else "POST", route,
                           body=None if body is None else json.dumps(body).encode(), headers=headers)
        with connection.getresponse() as response:
            return response.status, response.getheader("X-Request-Id"), response.read().decode()
    finally:
        connection.close()


def app_probe(url: str, token: str, expected: dict) -> list[str]:
    status, _, _ = request(url, "/health")
    if status not in (401, 403):
        raise ValueError("the service did not reject the anonymous probe")
    for path, payload in (("/health", {"status": "ok"}), ("/v1/model", expected["model"])):
        status, _, body = request(url, path, token)
        if status != 200 or json.loads(body) != payload:
            raise ValueError(f"verification failed for {path}")
    request_ids = []
    for _ in range(2):
        status, request_id, body = request(url, "/v1/predict", token, PROBE)
        if status != 200 or not request_id or json.loads(body) != expected:
            raise ValueError("prediction or release lineage differs from the recorded probe")
        request_ids.append(request_id)
    if len(set(request_ids)) != 2 or not all(re.fullmatch(r"[0-9a-f]{32}", item) for item in request_ids):
        raise ValueError("predictions must produce two distinct request IDs")
    status, _, body = request(url, "/metrics", token)
    release = expected["model"]
    label = (f'eddf_serving_model_info{{model_release_id="{release["model_release_id"]}",'
             f'model_version="{release["model_version"]}"}} 1.0')
    if status != 200 or label not in body.splitlines() or "eddf_prediction_request_duration_seconds_count" not in body:
        raise ValueError("serving metrics are missing the pinned model or latency count")
    return request_ids


def logs_for(project: str, revision: str, request_ids: list[str], release: str) -> list[dict]:
    match = " OR ".join(f'(jsonPayload.request_id="{item}" OR textPayload:"{item}")' for item in request_ids)
    query = f'resource.type="cloud_run_revision" AND resource.labels.revision_name="{revision}" AND ({match})'
    for attempt in range(12):
        entries = json.loads(gcloud("logging", "read", query, "--project", project, "--freshness=10m", "--limit=20", "--format=json"))
        found = {}
        for entry in entries:
            payload = entry.get("jsonPayload")
            if payload is None:
                raw = entry.get("textPayload", "")
                try:
                    payload = json.loads(raw[raw.index("{"):])
                except (ValueError, TypeError):
                    continue
            if (payload.get("request_id") in request_ids and payload.get("route") == "/v1/predict"
                    and payload.get("status") == 200 and payload.get("model_release_id") == release
                    and isinstance(payload.get("latency_ms"), (float, int))):
                key = payload["request_id"]
                found[key] = {"request_id": key, "latency_ms": payload["latency_ms"], "insert_id": entry.get("insertId")}
        if found.keys() == set(request_ids):
            return [found[item] for item in request_ids]
        if attempt < 11:
            time.sleep(5)
    raise ValueError("Cloud Logging did not return both correlated prediction records")


def verify(args) -> dict:
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,62}", args.revision):
        raise ValueError("invalid revision name")
    if not re.fullmatch(r"[a-z0-9.-]+-docker\.pkg\.dev/[a-z0-9_./-]+@sha256:[a-f0-9]{64}", args.image):
        raise ValueError("expected a digest-pinned Artifact Registry image")
    scope = ["--project", args.project, "--region", args.region, "--format=json"]
    service = json.loads(gcloud("run", "services", "describe", args.service, *scope))
    revision = json.loads(gcloud("run", "revisions", "describe", args.revision, *scope))
    reported_image = revision["spec"]["containers"][0]["image"]
    if reported_image != args.image or not any(c["type"] == "Ready" and c["status"] == "True"
                                              for c in revision["status"]["conditions"]):
        raise ValueError("the revision is not ready with the expected image")
    audience, url = target_url(service["status"], args.revision, args.tag)
    token = gcloud("auth", "print-identity-token", "--impersonate-service-account", args.invoker, "--audiences", audience)
    expected = json.loads(args.evidence.read_bytes())["probe"]
    ids = app_probe(url, token, expected)
    logs = logs_for(args.project, args.revision, ids, expected["model"]["model_release_id"])
    return {"project": args.project, "region": args.region, "service": args.service, "revision": args.revision,
            "image": args.image, "tag": args.tag, "traffic_percent": 0 if args.tag else 100,
            "anonymous_probe_denied": True, "probe": expected, "prediction_logs": logs}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("project", "region", "service", "revision", "image", "invoker"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--tag", help="verify a zero-traffic tagged candidate instead of the active revision")
    parser.add_argument("--evidence", type=Path, default=HERE / "evidence/cloud-run-image-rehearsal.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = verify(args)
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2, sort_keys=True)
            output.write("\n")
    except (KeyError, OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"Cloud Run acceptance: {exc}\n")


if __name__ == "__main__":
    main()
