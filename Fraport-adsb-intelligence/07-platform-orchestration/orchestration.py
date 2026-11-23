"""Verify a monthly Geometry v2 release and record its local Dagster handoff."""

import argparse
import importlib.util
import json
import os
import subprocess
import tempfile
from pathlib import Path

from dagster import (
    AssetExecutionContext,
    DagsterInstance,
    Definitions,
    EnvVar,
    Failure,
    FilesystemIOManager,
    MonthlyPartitionsDefinition,
    RetryPolicy,
    asset,
    define_asset_job,
    in_process_executor,
)

HERE = Path(__file__).resolve().parent
VERIFIER_PATH = HERE.parent / "04-aviation-lakehouse" / "release_inputs.py"
spec = importlib.util.spec_from_file_location("fraport_release_inputs", VERIFIER_PATH)
release_inputs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_inputs)

MONTHS = MonthlyPartitionsDefinition(start_date="2024-11", timezone="UTC", fmt="%Y-%m")
CONTROLS = ("manifest.json", "validation.json", "approval.json", "_SUCCESS")


def source_commit() -> str:
    return subprocess.check_output([
        "git", "log", "-1", "--format=%H", "HEAD", "--", "orchestration.py", "uv.lock", str(VERIFIER_PATH),
    ], cwd=HERE, text=True).strip()


def code_digests() -> dict:
    return {path.name: release_inputs.file_digest(path) for path in (
        Path(__file__), VERIFIER_PATH, HERE / "uv.lock",
    )}


def release_directory(month: str) -> Path:
    return Path(os.environ["FRAPORT_RELEASES_DIR"]) / f"geometry-v2-{month}"


def control_digests(directory: Path) -> dict:
    return {name: release_inputs.file_digest(directory / name) for name in CONTROLS}


@asset(partitions_def=MONTHS, description="Verified Geometry v2 monthly Gold release and label quality.")
def approved_gold(context: AssetExecutionContext) -> dict:
    directory = release_directory(context.partition_key)
    controls = control_digests(directory)
    lineage, labels = release_inputs.load_release(directory)
    counts = dict(release_inputs.check_silver(labels, lineage["release_id"]))
    if lineage["manifest_sha256"] != controls["manifest.json"] or control_digests(directory) != controls:
        raise Failure("Gold release metadata changed during verification")
    context.add_output_metadata({"release_id": lineage["release_id"], "rows": len(labels),
                                 "usable_labels": counts["labeled"], "manifest_sha256": lineage["manifest_sha256"]})
    return {**lineage, "control_sha256": controls, "source_commit": source_commit(),
            "code_sha256": code_digests(), "rows": len(labels), "coverage_status_counts": counts}


def write_handoff(output: Path, evidence: dict) -> bool:
    data = (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent) as staged:
        staged.write(data)
        staged.flush()
        try:
            os.link(staged.name, output)
        except FileExistsError:
            if output.read_bytes() != data:
                raise Failure(f"existing handoff for {evidence['release_id']} differs; review its lineage")
            return False
    return True


@asset(partitions_def=MONTHS, retry_policy=RetryPolicy(max_retries=1, delay=1),
       description="Local checkpoint for the verified monthly release.")
def local_handoff(context: AssetExecutionContext, approved_gold: dict) -> None:
    directory = release_directory(context.partition_key)
    if (approved_gold["release_id"] != directory.name or approved_gold["code_sha256"] != code_digests()
            or approved_gold["control_sha256"] != control_digests(directory)):
        raise Failure("Gold controls or verification code changed; reverify the partition", allow_retries=False)
    output = Path(os.environ["FRAPORT_STATE_DIR"]) / "handoffs" / f"{directory.name}.json"
    evidence = {"schema_version": "fraport-local-handoff-v1", "month_utc": context.partition_key,
                "status": "verified_local", **approved_gold}
    created = write_handoff(output, evidence)
    context.add_output_metadata({"release_id": directory.name, "handoff": str(output),
                                 "created": created, "source_commit": approved_gold["source_commit"]})


defs = Definitions(
    assets=[approved_gold, local_handoff],
    jobs=[
        define_asset_job("verify_month", selection=[approved_gold, local_handoff], executor_def=in_process_executor),
        define_asset_job("resume_local_handoff", selection=[local_handoff], executor_def=in_process_executor),
    ],
    resources={"io_manager": FilesystemIOManager(base_dir=EnvVar("FRAPORT_STATE_DIR"))},
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", choices=("verify_month", "resume_local_handoff"))
    parser.add_argument("month", help="UTC partition, YYYY-MM")
    args = parser.parse_args()
    for setting in ("DAGSTER_HOME", "FRAPORT_RELEASES_DIR", "FRAPORT_STATE_DIR"):
        if not os.environ.get(setting):
            parser.error(f"set {setting} before running the local job")
    if not MONTHS.has_partition_key(args.month):
        parser.error(f"unknown completed UTC month partition: {args.month}")
    with DagsterInstance.get() as instance:
        result = defs.resolve_job_def(args.job).execute_in_process(
            instance=instance, partition_key=args.month, raise_on_error=False,
        )
    print(json.dumps({"run_id": result.run_id, "job": args.job, "partition": args.month, "success": result.success}))
    if not result.success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
