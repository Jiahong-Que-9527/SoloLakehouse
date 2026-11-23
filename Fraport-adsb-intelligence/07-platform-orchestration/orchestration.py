"""Verify a monthly Geometry v2 release and rehearse its analytics ingestion."""

import argparse
import importlib.util
import json
import os
import re
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
    RunRequest,
    SkipReason,
    asset,
    define_asset_job,
    in_process_executor,
    sensor,
)

from local_analytics import PHASE_03, ingest_local

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


def handoff_path(month: str) -> Path:
    return Path(os.environ["FRAPORT_STATE_DIR"]) / "handoffs" / f"geometry-v2-{month}.json"


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
    output = handoff_path(context.partition_key)
    evidence = {"schema_version": "fraport-local-handoff-v1", "month_utc": context.partition_key,
                "status": "verified_local", **approved_gold}
    created = write_handoff(output, evidence)
    context.add_output_metadata({"release_id": directory.name, "handoff": str(output),
                                 "created": created, "source_commit": approved_gold["source_commit"]})


@asset(partitions_def=MONTHS, deps=[local_handoff], description="Rehearse phase 03 ingestion in local DuckDB.")
def local_analytics(context: AssetExecutionContext) -> dict:
    month = context.partition_key
    directory = release_directory(month)
    handoff = release_inputs.read_json(handoff_path(month))
    if (handoff["schema_version"] != "fraport-local-handoff-v1" or handoff["status"] != "verified_local"
            or handoff["release_id"] != directory.name or handoff["month_utc"] != month
            or handoff["code_sha256"] != code_digests() or handoff["control_sha256"] != control_digests(directory)):
        raise Failure("analytics requires an unchanged verified handoff for this partition", allow_retries=False)
    database = Path(os.environ["FRAPORT_STATE_DIR"]) / "analytics.duckdb"
    result = ingest_local(directory, handoff, database)
    result["handoff_sha256"] = release_inputs.file_digest(handoff_path(month))
    result["analytics_code_sha256"] = {path.name: release_inputs.file_digest(path)
                                       for path in (HERE / "local_analytics.py", PHASE_03)}
    context.add_output_metadata({"release_id": result["release_id"], "status": result["status"],
                                 "rows_added": result["rows_added"], **result["geometry_counts"]})
    return result


analytics_job = define_asset_job("ingest_month_local", selection=[approved_gold, local_handoff, local_analytics],
                                 executor_def=in_process_executor)


@sensor(job=analytics_job)
def geometry_release_ready():
    root = Path(os.environ["FRAPORT_RELEASES_DIR"])
    if not root.is_dir():
        return SkipReason("Geometry v2 release directory is unavailable")
    runs = []
    for directory in sorted(root.glob("geometry-v2-*")):
        month = directory.name.removeprefix("geometry-v2-")
        if not directory.is_dir() or not re.fullmatch(r"\d{4}-\d{2}", month) or not MONTHS.has_partition_key(month):
            continue
        if not all((directory / name).is_file() for name in CONTROLS):
            continue
        try:
            manifest_hash = release_inputs.file_digest(directory / "manifest.json")
        except FileNotFoundError:
            continue
        runs.append(RunRequest(run_key=f"{directory.name}:{manifest_hash}", partition_key=month))
    return runs or SkipReason("No completed monthly release with all gate files")


defs = Definitions(
    assets=[approved_gold, local_handoff, local_analytics],
    jobs=[
        define_asset_job("verify_month", selection=[approved_gold, local_handoff], executor_def=in_process_executor),
        define_asset_job("resume_local_handoff", selection=[local_handoff], executor_def=in_process_executor),
        analytics_job,
        define_asset_job("resume_local_analytics", selection=[local_analytics], executor_def=in_process_executor),
    ],
    sensors=[geometry_release_ready],
    resources={"io_manager": FilesystemIOManager(base_dir=EnvVar("FRAPORT_STATE_DIR"))},
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", choices=("verify_month", "resume_local_handoff", "ingest_month_local", "resume_local_analytics"))
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
    report = {"run_id": result.run_id, "job": args.job, "partition": args.month, "success": result.success}
    if result.success and args.job in ("ingest_month_local", "resume_local_analytics"):
        report["analytics"] = result.output_for_node("local_analytics")
    print(json.dumps(report))
    if not result.success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
