"""Dagster software-defined assets for the SoloLakehouse v2.5 runtime."""

from __future__ import annotations

import re
import time
from datetime import date, datetime, timezone
from io import BytesIO
from typing import Any

import pandas as pd
import structlog
from resources import MinioResource, PipelineConfigResource

from dagster import (
    AssetCheckResult,
    AssetKey,
    RetryPolicy,
    RunRequest,
    SkipReason,
    asset,
    asset_check,
    sensor,
)
from ingestion.collectors.dax_collector import DAXCollector
from ingestion.collectors.ecb_collector import ECBCollector
from ingestion.trino_sql import register_gold_tables_trino
from ml.evaluate import run_experiment_set
from transformations import dax_bronze_to_silver, ecb_bronze_to_silver, silver_to_gold_features

logger = structlog.get_logger()
PARTITION_RE = re.compile(r"ingestion_date=(\d{4}-\d{2}-\d{2})")


def _emit_metric(step: str, started_at: float) -> None:
    duration_ms = int((time.perf_counter() - started_at) * 1000)
    logger.info("pipeline_metric", metric="pipeline.step.duration_ms", step=step, value=duration_ms)


def _read_parquet_from_minio(minio_client: Any, bucket: str, path: str) -> pd.DataFrame:
    response = minio_client.get_object(bucket, path)
    try:
        return pd.read_parquet(BytesIO(response.read()))
    finally:
        response.close()
        response.release_conn()


def _latest_partition_date(minio_client: Any, bucket: str, prefix: str) -> date | None:
    latest: date | None = None
    for obj in minio_client.list_objects(bucket, prefix=prefix, recursive=True):
        match = PARTITION_RE.search(obj.object_name)
        if not match:
            continue
        candidate = datetime.strptime(match.group(1), "%Y-%m-%d").date()
        if latest is None or candidate > latest:
            latest = candidate
    return latest


@asset(group_name="bronze", retry_policy=RetryPolicy(max_retries=3, delay=5))
def ecb_bronze(
    context,
    minio: MinioResource,
    pipeline_config: PipelineConfigResource,
) -> dict[str, Any]:
    started = time.perf_counter()
    result = ECBCollector(
        minio_client=minio.get_client(),
        bucket=pipeline_config.bucket,
        force=False,
    ).collect()
    context.add_output_metadata(
        {
            "status": result.get("status", "ok"),
            "valid_count": int(result.get("valid_count", 0)),
            "rejected_count": int(result.get("rejected_count", 0)),
            "partition_date": date.today().isoformat(),
            "path": result.get("path", ""),
            "rejected_path": result.get("rejected_path") or "",
        }
    )
    _emit_metric("ecb_bronze", started)
    return result


@asset(group_name="bronze", retry_policy=RetryPolicy(max_retries=3, delay=5))
def dax_bronze(
    context,
    minio: MinioResource,
    pipeline_config: PipelineConfigResource,
) -> dict[str, Any]:
    started = time.perf_counter()
    result = DAXCollector(
        minio_client=minio.get_client(),
        bucket=pipeline_config.bucket,
        force=False,
    ).collect()
    context.add_output_metadata(
        {
            "status": result.get("status", "ok"),
            "valid_count": int(result.get("valid_count", 0)),
            "rejected_count": int(result.get("rejected_count", 0)),
            "partition_date": date.today().isoformat(),
            "path": result.get("path", ""),
            "rejected_path": result.get("rejected_path") or "",
        }
    )
    _emit_metric("dax_bronze", started)
    return result


@asset(group_name="silver")
def ecb_silver(
    context,
    minio: MinioResource,
    pipeline_config: PipelineConfigResource,
    ecb_bronze: dict[str, Any],
) -> str:
    _ = ecb_bronze
    started = time.perf_counter()
    minio_client = minio.get_client()
    silver_path = ecb_bronze_to_silver.run(
        minio_client=minio_client,
        bucket=pipeline_config.bucket,
    )
    silver_df = _read_parquet_from_minio(minio_client, pipeline_config.bucket, silver_path)
    context.add_output_metadata(
        {"silver_path": silver_path, "row_count": int(len(silver_df.index))}
    )
    _emit_metric("ecb_silver", started)
    return silver_path


@asset(group_name="silver")
def dax_silver(
    context,
    minio: MinioResource,
    pipeline_config: PipelineConfigResource,
    dax_bronze: dict[str, Any],
) -> str:
    _ = dax_bronze
    started = time.perf_counter()
    minio_client = minio.get_client()
    silver_path = dax_bronze_to_silver.run(
        minio_client=minio_client,
        bucket=pipeline_config.bucket,
    )
    silver_df = _read_parquet_from_minio(minio_client, pipeline_config.bucket, silver_path)
    context.add_output_metadata(
        {"silver_path": silver_path, "row_count": int(len(silver_df.index))}
    )
    _emit_metric("dax_silver", started)
    return silver_path


@asset(group_name="gold")
def gold_features(
    context,
    minio: MinioResource,
    pipeline_config: PipelineConfigResource,
    ecb_silver: str,
    dax_silver: str,
) -> str:
    _ = (ecb_silver, dax_silver)
    started = time.perf_counter()
    minio_client = minio.get_client()
    gold_path = silver_to_gold_features.run(
        minio_client=minio_client,
        bucket=pipeline_config.bucket,
    )
    gold_df = _read_parquet_from_minio(minio_client, pipeline_config.bucket, gold_path)
    register_gold_tables_trino(trino_url=pipeline_config.trino_url, bucket=pipeline_config.bucket)
    context.add_output_metadata({"gold_path": gold_path, "event_count": int(len(gold_df.index))})
    _emit_metric("gold_features", started)
    return gold_path


@asset(group_name="ml")
def ml_experiment(
    context,
    minio: MinioResource,
    pipeline_config: PipelineConfigResource,
    gold_features: str,
) -> str:
    _ = gold_features
    started = time.perf_counter()
    best_run_id = run_experiment_set(
        minio_client=minio.get_client(),
        mlflow_tracking_uri=pipeline_config.mlflow_tracking_uri,
        bucket=pipeline_config.bucket,
        trino_url=pipeline_config.trino_url,
    )
    context.add_output_metadata({"best_run_id": best_run_id})
    _emit_metric("ml_experiment", started)
    return best_run_id


@sensor(job_name="full_pipeline_job", minimum_interval_seconds=1800)
def ecb_data_freshness_sensor(minio: MinioResource, pipeline_config: PipelineConfigResource):
    latest = _latest_partition_date(
        minio_client=minio.get_client(),
        bucket=pipeline_config.bucket,
        prefix="bronze/ecb_rates/",
    )
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


@asset_check(asset=gold_features, description="gold_features should contain at least 10 rows")
def gold_features_min_rows_check(
    minio: MinioResource,
    pipeline_config: PipelineConfigResource,
    gold_features: str,
) -> AssetCheckResult:
    gold_df = _read_parquet_from_minio(
        minio_client=minio.get_client(),
        bucket=pipeline_config.bucket,
        path=gold_features,
    )
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
