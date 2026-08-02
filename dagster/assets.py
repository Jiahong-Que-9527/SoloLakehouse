"""Dagster software-defined assets for the SoloLakehouse v2.5 runtime."""

from __future__ import annotations

import time
from datetime import date, datetime, timezone
from typing import Any

import pandas as pd
import structlog
from resources import IcebergCatalogResource, PipelineConfigResource

from dagster import (
    AssetCheckResult,
    AssetKey,
    DagsterRunStatus,
    DefaultSensorStatus,
    RetryPolicy,
    RunRequest,
    RunStatusSensorContext,
    SkipReason,
    asset,
    asset_check,
    run_status_sensor,
    sensor,
)
from governance.contracts import contract_for_asset_key
from governance.emission import emit_pending_lineage_evidence_for_run
from governance.ml_lineage import build_ml_lineage_tuple, contract_content_sha256
from ingestion import iceberg_io
from ingestion.collectors.dax_collector import DAXCollector
from ingestion.collectors.ecb_collector import ECBCollector
from ml.evaluate import run_experiment_set
from ml.train_ecb_dax_model import FEATURE_VERSION
from transformations import dax_bronze_to_silver, ecb_bronze_to_silver, silver_to_gold_features

logger = structlog.get_logger()


def _emit_metric(step: str, started_at: float) -> None:
    duration_ms = int((time.perf_counter() - started_at) * 1000)
    logger.info("pipeline_metric", metric="pipeline.step.duration_ms", step=step, value=duration_ms)


def _metadata_row_count(result: dict[str, Any]) -> int:
    row_count = result.get("row_count", 0)
    if isinstance(row_count, bool):
        return int(row_count)
    if isinstance(row_count, int | float | str):
        return int(row_count)
    return 0


def _governed_asset_metadata(
    catalog,
    asset_key: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    contract = contract_for_asset_key(asset_key)
    if contract is None:
        return metadata
    location = contract.physical_location
    snapshot_id = iceberg_io.current_snapshot_id(catalog, location.namespace, location.table)
    return {**metadata, "iceberg_snapshot_id": snapshot_id}


@asset(group_name="bronze", retry_policy=RetryPolicy(max_retries=3, delay=5))
def ecb_bronze(
    context,
    iceberg_catalog: IcebergCatalogResource,
    pipeline_config: PipelineConfigResource,
) -> dict[str, Any]:
    started = time.perf_counter()
    catalog = iceberg_catalog.get_catalog()
    result = ECBCollector(
        catalog=catalog,
        bucket=pipeline_config.bucket,
        force=False,
    ).collect()
    context.add_output_metadata(
        _governed_asset_metadata(
            catalog,
            "ecb_bronze",
            {
                "status": result.get("status", "ok"),
                "valid_count": int(result.get("valid_count", 0)),
                "rejected_count": int(result.get("rejected_count", 0)),
                "partition_date": date.today().isoformat(),
                "path": result.get("path", ""),
                "rejected_path": result.get("rejected_path") or "",
            },
        )
    )
    _emit_metric("ecb_bronze", started)
    return result


@asset(group_name="bronze", retry_policy=RetryPolicy(max_retries=3, delay=5))
def dax_bronze(
    context,
    iceberg_catalog: IcebergCatalogResource,
    pipeline_config: PipelineConfigResource,
) -> dict[str, Any]:
    started = time.perf_counter()
    catalog = iceberg_catalog.get_catalog()
    result = DAXCollector(
        catalog=catalog,
        bucket=pipeline_config.bucket,
        force=False,
    ).collect()
    context.add_output_metadata(
        _governed_asset_metadata(
            catalog,
            "dax_bronze",
            {
                "status": result.get("status", "ok"),
                "valid_count": int(result.get("valid_count", 0)),
                "rejected_count": int(result.get("rejected_count", 0)),
                "partition_date": date.today().isoformat(),
                "path": result.get("path", ""),
                "rejected_path": result.get("rejected_path") or "",
            },
        )
    )
    _emit_metric("dax_bronze", started)
    return result


@asset(group_name="silver")
def ecb_silver(
    context,
    iceberg_catalog: IcebergCatalogResource,
    ecb_bronze: dict[str, Any],
) -> str:
    _ = ecb_bronze
    started = time.perf_counter()
    catalog = iceberg_catalog.get_catalog()
    result = ecb_bronze_to_silver.run(catalog)
    context.add_output_metadata(
        _governed_asset_metadata(
            catalog,
            "ecb_silver",
            {"table": result["table"], "row_count": _metadata_row_count(result)},
        )
    )
    _emit_metric("ecb_silver", started)
    return str(result["table"])


@asset(group_name="silver")
def dax_silver(
    context,
    iceberg_catalog: IcebergCatalogResource,
    dax_bronze: dict[str, Any],
) -> str:
    _ = dax_bronze
    started = time.perf_counter()
    catalog = iceberg_catalog.get_catalog()
    result = dax_bronze_to_silver.run(catalog)
    context.add_output_metadata(
        _governed_asset_metadata(
            catalog,
            "dax_silver",
            {"table": result["table"], "row_count": _metadata_row_count(result)},
        )
    )
    _emit_metric("dax_silver", started)
    return str(result["table"])


@asset(group_name="gold")
def gold_features(
    context,
    iceberg_catalog: IcebergCatalogResource,
    ecb_silver: str,
    dax_silver: str,
) -> str:
    _ = (ecb_silver, dax_silver)
    started = time.perf_counter()
    catalog = iceberg_catalog.get_catalog()
    result = silver_to_gold_features.run(catalog)
    context.add_output_metadata(
        _governed_asset_metadata(
            catalog,
            "gold_features",
            {"table": result["table"], "event_count": _metadata_row_count(result)},
        )
    )
    _emit_metric("gold_features", started)
    return str(result["table"])


@asset(group_name="ml")
def ml_experiment(
    context,
    iceberg_catalog: IcebergCatalogResource,
    pipeline_config: PipelineConfigResource,
    gold_features: str,
) -> str:
    _ = gold_features
    started = time.perf_counter()
    catalog = iceberg_catalog.get_catalog()
    contract = contract_for_asset_key("gold_features")
    if contract is None:
        raise ValueError("gold_features is not covered by a governed dataset contract")
    location = contract.physical_location
    snapshot_id = iceberg_io.current_snapshot_id(catalog, location.namespace, location.table)
    lineage = build_ml_lineage_tuple(
        iceberg_snapshot_id=snapshot_id,
        dagster_run_id=context.run_id,
        feature_version=FEATURE_VERSION,
        data_contract_hash=contract_content_sha256(contract),
    )
    best_run_id = run_experiment_set(
        catalog=catalog,
        mlflow_tracking_uri=pipeline_config.mlflow_tracking_uri,
        lineage=lineage,
    )
    context.add_output_metadata(
        {
            "best_run_id": best_run_id,
            "ml_lineage_sha256": lineage.sha256(),
            **lineage.model_dump(mode="json"),
        }
    )
    _emit_metric("ml_experiment", started)
    return best_run_id


@sensor(job_name="full_pipeline_job", minimum_interval_seconds=1800)
def ecb_data_freshness_sensor(
    iceberg_catalog: IcebergCatalogResource,
):
    from pyiceberg.exceptions import NoSuchTableError

    catalog = iceberg_catalog.get_catalog()
    latest: date | None = None

    try:
        df = iceberg_io.scan_table(catalog, "bronze", "ecb_rates")
        if not df.empty:
            latest = pd.to_datetime(df["_ingestion_timestamp"], utc=True).max().date()
    except NoSuchTableError:
        pass

    if latest is None:
        return RunRequest(
            run_key=f"ecb-freshness-init-{datetime.now(timezone.utc).isoformat()}",
            asset_selection=[AssetKey("ecb_bronze")],
        )

    lag_hours = (datetime.now(timezone.utc).date() - latest).days * 24
    if lag_hours >= 48:
        return RunRequest(
            run_key=f"ecb-freshness-{latest.isoformat()}",
            asset_selection=[AssetKey("ecb_bronze")],
        )
    return SkipReason(
        f"ECB data fresh enough: latest partition {latest.isoformat()} ({lag_hours}h lag)"
    )


@run_status_sensor(
    run_status=DagsterRunStatus.SUCCESS,
    minimum_interval_seconds=30,
    name="lineage_evidence_sensor",
    default_status=DefaultSensorStatus.RUNNING,
    monitor_all_code_locations=True,
)
def lineage_evidence_sensor(context: RunStatusSensorContext):
    """Emit lineage evidence for every governed asset materialized in a successful run."""
    run_id = context.dagster_run.run_id
    result = emit_pending_lineage_evidence_for_run(run_id)
    if result.skip_reason is not None:
        yield SkipReason(result.skip_reason)
        return
    for emission in result.emissions:
        logger.info(
            "lineage_evidence_emitted",
            run_id=run_id,
            dataset_id=emission.dataset_id,
            object_path=emission.object_path,
            record_sha256=emission.record_sha256,
        )
    yield SkipReason(
        f"emitted {len(result.emissions)} lineage evidence manifest(s) for run {run_id}"
    )


@asset_check(asset=gold_features, description="gold_features should contain at least 10 rows")
def gold_features_min_rows_check(
    iceberg_catalog: IcebergCatalogResource,
    gold_features: str,
) -> AssetCheckResult:
    _ = gold_features
    catalog = iceberg_catalog.get_catalog()
    gold_df = iceberg_io.scan_table(catalog, "gold", "ecb_dax_features")
    row_count = int(len(gold_df.index))
    passed = row_count >= 10
    return AssetCheckResult(
        passed=passed,
        description=(
            "gold_features has enough event rows for event-study modeling"
            if passed
            else "gold_features has fewer than 10 rows"
        ),
        metadata={"row_count": row_count},
    )
