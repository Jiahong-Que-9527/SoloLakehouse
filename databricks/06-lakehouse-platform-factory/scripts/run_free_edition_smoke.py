"""Smoke-test D06's reference job in a Free Edition workspace with one identity."""

import argparse
import json
import subprocess
import time
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

from verify_stack_contract import PROJECT, validate_bundle

REFERENCE = "reference"
INVALID = " "


def task_results(tasks):
    attempts_by_task = {}
    for task in tasks:
        attempts_by_task.setdefault(task["task_key"], []).append(
            {
                "attempt_number": task.get("attempt_number", 0),
                "task_run_id": task["run_id"],
                "result_state": task["state"].get("result_state"),
            }
        )
    results = {}
    for name, attempts in attempts_by_task.items():
        ordered = sorted(attempts, key=lambda attempt: attempt["attempt_number"])
        results[name] = ordered[-1]
        if len(ordered) > 1:
            results[name]["previous_attempts"] = ordered[:-1]
    return results


def smoke(cli, profile, git_sha):
    def db(*args):
        output = subprocess.check_output([cli, *args, "-p", profile, "-o", "json"], text=True)
        return json.loads(output) if output.strip() else None

    def submit(label, tasks):
        run = db(
            "jobs",
            "submit",
            "--no-wait",
            "--json",
            json.dumps({"run_name": f"{stack_id} / {label}", "tasks": tasks}),
        )
        run_id = str(run["run_id"])
        print(f"{label} run {run_id}", flush=True)
        deadline = time.monotonic() + 720
        while True:
            run = db("jobs", "get-run", run_id)
            state = run["state"]["life_cycle_state"]
            if state in {"TERMINATED", "SKIPPED", "INTERNAL_ERROR"}:
                break
            if time.monotonic() > deadline:
                raise TimeoutError(f"{label} run {run_id} remained {state}")
            time.sleep(6)
        return {
            "run_id": run["run_id"],
            "run_url": run["run_page_url"],
            "result_state": run["state"]["result_state"],
            "tasks": task_results(run["tasks"]),
        }

    def task_output(report, name):
        run_id = report["tasks"][name]["task_run_id"]
        return db("jobs", "get-run-output", str(run_id))

    def notebook_result(report, name):
        output = task_output(report, name)
        result = output.get("notebook_output")
        if not result or result.get("truncated"):
            raise AssertionError(output.get("error", f"No full output for {name}"))
        return json.loads(result["result"])

    principal = db("current-user", "me")["userName"]
    stack_id = f"slh-d06smoke{datetime.now(UTC):%Y%m%d%H%M%S}-dev"
    root = f"/Workspace/Users/{principal}/d06-reference-smoke/{stack_id}"
    mock_owner = "factory-deployer@example.invalid"
    bundle_inputs = {
        "bundle_target": "dev",
        "bundle_vars": {
            "stack_id": stack_id,
            "catalog": "workspace",
            "owner": mock_owner,
            "runtime_service_principal": "11111111-1111-4111-8111-111111111111",
            **{
                f"{layer}_schema": f"{stack_id.replace('-', '_')}_{layer}"
                for layer in ("bronze", "silver", "gold")
            },
        },
    }
    bundle = validate_bundle(cli, bundle_inputs, mock_owner)
    (job,) = bundle["resources"]["jobs"].values()
    # The Bundle stays unchanged. Only the resolved tasks are submitted to Free Edition.
    db("workspace", "mkdirs", root)
    for source in ("reference_batch.py", "free_edition_smoke_setup.py"):
        db(
            "workspace",
            "import",
            f"{root}/{Path(source).stem}",
            "--file",
            str(PROJECT / "notebooks" / source),
            "--format",
            "SOURCE",
            "--language",
            "PYTHON",
        )

    def setup_task(phase):
        return {
            "task_key": phase,
            "timeout_seconds": 120,
            "notebook_task": {
                "notebook_path": f"{root}/free_edition_smoke_setup",
                "base_parameters": {"phase": phase, "stack_id": stack_id},
            },
        }

    def batch_tasks(value):
        tasks = deepcopy(job["tasks"])
        for task in tasks:
            nb = task["notebook_task"]
            nb["notebook_path"] = f"{root}/reference_batch"
            nb["base_parameters"]["fixture_value"] = value
        return tasks

    first_tasks = batch_tasks(REFERENCE)
    land = next(task for task in first_tasks if task["task_key"] == "land")
    land["depends_on"] = [{"task_key": "prepare"}]
    first = submit("first", [setup_task("prepare"), *first_tasks])
    assert first["result_state"] == "SUCCESS", first
    setup = notebook_result(first, "prepare")
    initial = notebook_result(first, "publish")
    assert initial.pop("run_as") == principal

    replay = submit("replay", batch_tasks(REFERENCE))
    assert replay["result_state"] == "SUCCESS", replay
    repeated = notebook_result(replay, "publish")
    assert repeated.pop("run_as") == principal
    assert repeated == initial

    rejected = submit("reject", batch_tasks(INVALID))
    assert rejected["result_state"] == "FAILED", rejected
    error = task_output(rejected, "quality").get("error", "")
    assert "Silver fixture_value must be non-empty" in error, error
    assert rejected["tasks"]["publish"]["result_state"] in {
        "UPSTREAM_FAILED",
        "UPSTREAM_CANCELED",
        "EXCLUDED",
        "SKIPPED",
    }, rejected

    checked = submit("inspect", [setup_task("inspect")])
    assert checked["result_state"] == "SUCCESS", checked
    final = notebook_result(checked, "inspect")["rows"]
    assert final["gold"] == [initial["row"]]
    assert len(final["silver"]) == 1 and final["silver"][0]["fixture_value"] == INVALID
    return {
        "git_sha": git_sha,
        "stack": setup,
        "scope": "reference job on Free Edition with one workspace identity",
        "runtime_identity_matches_authenticated_workspace_user": True,
        "first": first,
        "replay": replay,
        "reject": {**rejected, "expected_error": "Silver fixture_value must be non-empty"},
        "inspect": checked,
        "initial_gold": initial,
        "final_rows": final,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", default="databricks")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT, text=True).strip()
    data = smoke(args.cli, args.profile, git_sha)
    args.evidence.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    print(f"Evidence saved to {args.evidence}")


if __name__ == "__main__":
    main()
