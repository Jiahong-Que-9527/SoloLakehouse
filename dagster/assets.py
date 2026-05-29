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
    RetryPolicy,
    RunRequest,
    SkipReason,
    asset,
    asset_check,
    sensor,
)
from ingestion import iceberg_io
from ingestion.collectors.dax_collector import DAXCollector
from ingestion.collectors.ecb_collector import ECBCollector
from ml.evaluate import run_experiment_set
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
    iceberg_catalog: IcebergCatalogResource,
    ecb_bronze: dict[str, Any],
) -> str:
    _ = ecb_bronze
    started = time.perf_counter()
    result = ecb_bronze_to_silver.run(iceberg_catalog.get_catalog())
    context.add_output_metadata(
        {"table": result["table"], "row_count": _metadata_row_count(result)}
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
    result = dax_bronze_to_silver.run(iceberg_catalog.get_catalog())
    context.add_output_metadata(
        {"table": result["table"], "row_count": _metadata_row_count(result)}
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
    result = silver_to_gold_features.run(iceberg_catalog.get_catalog())
    context.add_output_metadata(
        {"table": result["table"], "event_count": _metadata_row_count(result)}
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
    best_run_id = run_experiment_set(
        catalog=iceberg_catalog.get_catalog(),
        mlflow_tracking_uri=pipeline_config.mlflow_tracking_uri,
        trino_url=pipeline_config.trino_url,
    )
    context.add_output_metadata({"best_run_id": best_run_id})
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
