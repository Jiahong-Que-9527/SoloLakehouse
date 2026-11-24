"""Check mock Terraform plans and convert their real outputs into Bundle inputs."""

import argparse
import json
import os
import subprocess
import tempfile
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Thread
from urllib.parse import urlsplit

from stack_paths import stack_paths

PROJECT = Path(__file__).resolve().parents[1]
LAYERS = ("bronze", "silver", "gold")
RUNTIME_PRIVILEGES = {"USE_SCHEMA", "CREATE_TABLE", "SELECT", "MODIFY"}


@contextmanager
def workspace_stub(owner):
    """Authenticate Bundle validation locally without live workspace credentials."""

    current_user_requested = Event()

    class WorkspaceHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            path = urlsplit(self.path).path
            if path == "/api/2.0/preview/scim/v2/Me":
                current_user_requested.set()
                body = {
                    "id": "123",
                    "userName": owner,
                    "displayName": "Factory Validator",
                    "active": True,
                }
            elif path == "/api/2.0/workspace/get-status":
                body = {"object_id": 456, "object_type": "DIRECTORY"}
            elif path == "/api/2.0/permissions/directories/456":
                body = {"object_id": "/directories/456", "access_control_list": []}
            else:
                self.send_error(404)
                return
            payload = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), WorkspaceHandler) as server:
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}", current_user_requested
        finally:
            server.shutdown()
            worker.join()


def validate_bundle(cli, outputs, owner):
    # Remove the caller's profiles, host, authentication, and bundle overrides from this child.
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("DATABRICKS_", "BUNDLE_VAR_", "DATABRICKS_BUNDLE_"))
    }
    with (
        workspace_stub(owner) as (host, current_user_requested),
        tempfile.TemporaryDirectory() as temp,
    ):
        config = Path(temp) / "databrickscfg"
        config.write_text(f"[d06-local]\nhost = {host}\ntoken = local-stub-only\n")
        env["DATABRICKS_CONFIG_FILE"] = str(config)
        args = [
            cli,
            "bundle",
            "validate",
            "--strict",
            "-o",
            "json",
            "-p",
            "d06-local",
            "-t",
            outputs["bundle_target"],
        ]
        for name, value in outputs["bundle_vars"].items():
            args.extend(["--var", f"{name}={value}"])
        result = subprocess.run(
            args, cwd=PROJECT, env=env, check=True, capture_output=True, text=True, timeout=30
        )
        assert current_user_requested.is_set(), "CLI did not authenticate against the local stub"
    return json.loads(result.stdout)


def verify_stack(plan, cfg, cli, state_root):
    values = plan["resource_changes"]
    assert all(resource["change"]["actions"] == ["create"] for resource in values)
    resources = {resource["address"]: resource["change"]["after"] for resource in values}
    assert len(resources) == 2 * len(LAYERS)
    outputs = {name: change["after"] for name, change in plan["output_changes"].items()}
    bundle_vars = outputs["bundle_vars"]
    backend = stack_paths(cfg, state_root)
    stack_id = backend["stack_id"]
    assert outputs["stack_id"] == bundle_vars["stack_id"] == stack_id
    assert outputs["bundle_target"] == cfg["environment"]
    assert bundle_vars["catalog"] == cfg["catalog"]
    for layer in LAYERS:
        name = bundle_vars[f"{layer}_schema"]
        expected_name = f"{stack_id.replace('-', '_')}_{layer}"
        schema = resources[f'databricks_schema.layers["{layer}"]']
        assert schema["name"] == name == expected_name
        assert schema["catalog_name"] == cfg["catalog"]
        assert schema["force_destroy"] == cfg["disposable"]
        grants = resources[f'databricks_grants.layers["{layer}"]']
        assert grants["schema"] == f"{cfg['catalog']}.{name}"
        access = {entry["principal"]: set(entry["privileges"]) for entry in grants["grant"]}
        expected_access = {cfg["runtime_service_principal"]: RUNTIME_PRIVILEGES}
        if layer == "gold":
            expected_access[cfg["reader_principal"]] = {"USE_SCHEMA", "SELECT"}
        assert access == expected_access

    try:
        bundle = validate_bundle(cli, outputs, cfg["owner"])
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"Bundle validation failed for {stack_id}: {error.stderr}") from error
    (job,) = bundle["resources"]["jobs"].values()
    assert job["name"] == outputs["job_name"] == f"{stack_id}-batch"
    assert bundle["bundle"]["target"] == cfg["environment"]
    assert bundle["run_as"]["service_principal_name"] == cfg["runtime_service_principal"]
    assert bundle["permissions"] == [
        {"level": "CAN_MANAGE", "user_name": cfg["owner"]},
        {"level": "CAN_RUN", "service_principal_name": cfg["runtime_service_principal"]},
    ]
    assert bundle["workspace"]["root_path"].endswith(f"/d06-batch-lakehouse/{stack_id}")
    tasks = {
        task["task_key"]: [dep["task_key"] for dep in task.get("depends_on", [])]
        for task in job["tasks"]
    }
    assert len(job["tasks"]) == len(tasks) == 4
    assert tasks == {
        "land": [],
        "transform": ["land"],
        "quality": ["transform"],
        "publish": ["quality"],
    }
    for task in job["tasks"]:
        notebook = task["notebook_task"]
        files = bundle["workspace"]["file_path"]
        assert notebook["notebook_path"] == f"{files}/notebooks/reference_batch"
        params = notebook["base_parameters"]
        assert params["phase"] == task["task_key"]
        for key in ("stack_id", "catalog", *(f"{layer}_schema" for layer in LAYERS)):
            assert params[key] == bundle_vars[key]
    schedule = job.get("schedule")
    if cfg["environment"] == "dev":
        assert schedule is None
    else:
        assert schedule["pause_status"] == "PAUSED"
    return {
        **backend,
        "schemas": [bundle_vars[f"{layer}_schema"] for layer in LAYERS],
        "catalog": bundle_vars["catalog"],
        "job": job["name"],
        "target": bundle["bundle"]["target"],
        "bundle_root": bundle["workspace"]["root_path"],
        "runtime": bundle["run_as"]["service_principal_name"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("test_log", type=Path)
    parser.add_argument("--cli", default="databricks")
    args = parser.parse_args()
    events = [json.loads(line) for line in args.test_log.read_text().splitlines()]
    plans = {
        event["@testrun"]: event["test_plan"] for event in events if event["type"] == "test_plan"
    }
    (summary,) = [event["test_summary"] for event in events if event["type"] == "test_summary"]
    assert summary["status"] == "pass" and summary["passed"] == 3
    with tempfile.TemporaryDirectory(prefix="d06-state-") as root:
        stacks = []
        for name in ("alpha", "bravo"):
            cfg = json.loads((PROJECT / "stacks" / f"{name}.tfvars.json").read_text())["stack"]
            stacks.append(verify_stack(plans[name], cfg, args.cli, Path(root)))
    alpha, bravo = stacks
    for key in ("stack_id", "state", "data_dir", "job", "target", "bundle_root", "runtime"):
        assert alpha[key] != bravo[key], key
    assert set(alpha["schemas"]).isdisjoint(bravo["schemas"])
    print(
        json.dumps(
            {"validation": "mock Terraform plan and local Bundle validation", "stacks": stacks},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
