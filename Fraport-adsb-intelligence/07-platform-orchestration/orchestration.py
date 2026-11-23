"""Verify a monthly Geometry v2 release and rehearse its analytics ingestion."""

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from dagster import (
    AssetDep,
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
    TimeWindowPartitionMapping,
    asset,
    define_asset_job,
    in_process_executor,
    sensor,
)

from cloud_analytics import reconcile_existing_release
from local_analytics import PHASE_03, ingest_local, phase03
from model_pipeline import features_for, replay_model

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


def verified_handoff(month: str) -> tuple[Path, dict, str]:
    directory = release_directory(month)
    raw = handoff_path(month).read_bytes()
    handoff = json.loads(raw)
    if (handoff["schema_version"] != "fraport-local-handoff-v1" or handoff["status"] != "verified_local"
            or handoff["release_id"] != directory.name or handoff["month_utc"] != month
            or handoff["code_sha256"] != code_digests() or handoff["control_sha256"] != control_digests(directory)):
        raise Failure("analytics requires an unchanged verified handoff for this partition", allow_retries=False)
    return directory, handoff, hashlib.sha256(raw).hexdigest()


@asset(partitions_def=MONTHS, deps=[local_handoff], description="Rehearse phase 03 ingestion in local DuckDB.")
def local_analytics(context: AssetExecutionContext) -> dict:
    directory, handoff, handoff_sha = verified_handoff(context.partition_key)
    database = Path(os.environ["FRAPORT_STATE_DIR"]) / "analytics.duckdb"
    result = ingest_local(directory, handoff, database)
    result["handoff_sha256"] = handoff_sha
    result["analytics_code_sha256"] = {path.name: release_inputs.file_digest(path)
                                       for path in (HERE / "local_analytics.py", PHASE_03)}
    context.add_output_metadata({"release_id": result["release_id"], "status": result["status"],
                                 "rows_added": result["rows_added"], **result["geometry_counts"]})
    return result


@asset(partitions_def=MONTHS, deps=[local_handoff], description="Read-only reconciliation of an existing BigQuery release.")
def bigquery_reconciliation(context: AssetExecutionContext) -> dict:
    directory, handoff, handoff_sha = verified_handoff(context.partition_key)
    verdict = phase03.verify_release(directory)
    if not verdict.ok or control_digests(directory) != handoff["control_sha256"]:
        raise Failure(f"phase 03 could not reverify the pinned release: {verdict.reason}", allow_retries=False)
    result = reconcile_existing_release(os.environ["FRAPORT_BQ_PROJECT"], handoff)
    result["handoff_sha256"] = handoff_sha
    result["cloud_analytics_sha256"] = release_inputs.file_digest(HERE / "cloud_analytics.py")
    context.add_output_metadata({"release_id": result["release_id"], "status": result["status"],
                                 "rows_added": result["rows_added"], "job_id": result["job_id"],
                                 "bytes_billed": result["bytes_billed"], **result["geometry_counts"]})
    return result


def monthly_feature_artifact(month: str, *, build: bool) -> dict:
    directory, handoff, _ = verified_handoff(month)
    verdict = phase03.verify_release(directory)
    if not verdict.ok:
        raise Failure(f"cannot build features from an unverified release: {verdict.reason}", allow_retries=False)
    return features_for(Path(os.environ["FRAPORT_SILVER_ROOT"]), Path(os.environ["FRAPORT_STATE_DIR"]),
                        directory, handoff, build=build)


@asset(partitions_def=MONTHS, deps=[local_handoff], description="Build or reuse phase 04 point-in-time features.")
def monthly_features(context: AssetExecutionContext) -> dict:
    result = monthly_feature_artifact(context.partition_key, build=True)
    context.add_output_metadata(result)
    return result


@asset(partitions_def=MONTHS, deps=[AssetDep(monthly_features, partition_mapping=TimeWindowPartitionMapping(end_offset=1))],
       description="Replay the pinned November candidate and December holdout in the M4 image.")
def container_training(context: AssetExecutionContext) -> dict:
    if context.partition_key != "2024-11":
        raise Failure("the pinned M4 replay uses the 2024-11 training partition", allow_retries=False)
    training = monthly_feature_artifact("2024-11", build=False)
    evaluation = monthly_feature_artifact("2024-12", build=False)
    result = replay_model(Path(os.environ["FRAPORT_STATE_DIR"]), training, evaluation,
                          Path(os.environ["FRAPORT_BASELINE_REPORT"]), os.environ.get("FRAPORT_DOCKER", "docker"))
    context.add_output_metadata({"model_release_id": result["model_release_id"], "image_id": result["image_id"],
                                 "directory": result["directory"], "reused": result["reused"],
                                 "source_commit": source_commit()})
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
    assets=[approved_gold, local_handoff, local_analytics, bigquery_reconciliation, monthly_features, container_training],
    jobs=[
        define_asset_job("verify_month", selection=[approved_gold, local_handoff], executor_def=in_process_executor),
        define_asset_job("resume_local_handoff", selection=[local_handoff], executor_def=in_process_executor),
        analytics_job,
        define_asset_job("resume_local_analytics", selection=[local_analytics], executor_def=in_process_executor),
        define_asset_job("reconcile_month_bigquery", selection=[bigquery_reconciliation], executor_def=in_process_executor),
        define_asset_job("build_month_features", selection=[approved_gold, local_handoff, monthly_features], executor_def=in_process_executor),
        define_asset_job("resume_month_features", selection=[monthly_features], executor_def=in_process_executor),
        define_asset_job("replay_model_month", selection=[container_training], executor_def=in_process_executor),
    ],
    sensors=[geometry_release_ready],
    resources={"io_manager": FilesystemIOManager(base_dir=EnvVar("FRAPORT_STATE_DIR"))},
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", choices=("verify_month", "resume_local_handoff", "ingest_month_local",
                                        "resume_local_analytics", "reconcile_month_bigquery", "build_month_features",
                                        "resume_month_features", "replay_model_month"))
    parser.add_argument("month", help="UTC partition, YYYY-MM")
    args = parser.parse_args()
    for setting in ("DAGSTER_HOME", "FRAPORT_RELEASES_DIR", "FRAPORT_STATE_DIR"):
        if not os.environ.get(setting):
            parser.error(f"set {setting} before running the local job")
    if args.job == "reconcile_month_bigquery" and not os.environ.get("FRAPORT_BQ_PROJECT"):
        parser.error("set FRAPORT_BQ_PROJECT before reconciling BigQuery")
    if args.job in ("build_month_features", "resume_month_features", "replay_model_month") and not os.environ.get("FRAPORT_SILVER_ROOT"):
        parser.error("set FRAPORT_SILVER_ROOT before building features or replaying training")
    if args.job == "replay_model_month" and not os.environ.get("FRAPORT_BASELINE_REPORT"):
        parser.error("set FRAPORT_BASELINE_REPORT before replaying training")
    if not MONTHS.has_partition_key(args.month):
        parser.error(f"unknown completed UTC month partition: {args.month}")
    with DagsterInstance.get() as instance:
        result = defs.resolve_job_def(args.job).execute_in_process(
            instance=instance, partition_key=args.month, raise_on_error=False,
        )
    report = {"run_id": result.run_id, "job": args.job, "partition": args.month, "success": result.success}
    if result.success and args.job in ("ingest_month_local", "resume_local_analytics"):
        report["analytics"] = result.output_for_node("local_analytics")
    if result.success and args.job == "reconcile_month_bigquery":
        report["analytics"] = result.output_for_node("bigquery_reconciliation")
    if result.success and args.job in ("build_month_features", "resume_month_features"):
        report["features"] = result.output_for_node("monthly_features")
    if result.success and args.job == "replay_model_month":
        report["training"] = result.output_for_node("container_training")
    print(json.dumps(report))
    if not result.success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
