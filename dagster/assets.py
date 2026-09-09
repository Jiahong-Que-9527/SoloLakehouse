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
    AssetCheckSeverity,
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
from governance.policy_hooks import validate_ml_training_allowed
from governance.quality import evaluate_max_staleness
from ingestion import iceberg_io
from ingestion.collectors.ecb_collector import ECBCollector
from ingestion.collectors.ecb_fx_collector import ECBFxCollector
from ingestion.collectors.ewg_collector import EWGCollector
from ml.evaluate import run_experiment_set
from ml.train_ecb_dax_model import FEATURE_VERSION
from transformations import (
    build_eur_market_daily,
    dax_bronze_to_silver,
    ecb_bronze_to_silver,
    ecb_fx_bronze_to_silver,
    silver_to_gold_features,
)

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
def german_equity_proxy_bronze(
    context,
    iceberg_catalog: IcebergCatalogResource,
    pipeline_config: PipelineConfigResource,
) -> dict[str, Any]:
    started = time.perf_counter()
    catalog = iceberg_catalog.get_catalog()
    result = EWGCollector(
        catalog=catalog,
        bucket=pipeline_config.bucket,
        force=False,
    ).collect()
    context.add_output_metadata(
        _governed_asset_metadata(
            catalog,
            "german_equity_proxy_bronze",
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
    _emit_metric("german_equity_proxy_bronze", started)
    return result


@asset(group_name="bronze", retry_policy=RetryPolicy(max_retries=3, delay=5))
def ecb_fx_bronze(
    context,
    iceberg_catalog: IcebergCatalogResource,
    pipeline_config: PipelineConfigResource,
) -> dict[str, Any]:
    started = time.perf_counter()
    catalog = iceberg_catalog.get_catalog()
    result = ECBFxCollector(
        catalog=catalog,
        bucket=pipeline_config.bucket,
        force=False,
    ).collect()
    context.add_output_metadata(
        _governed_asset_metadata(
            catalog,
            "ecb_fx_bronze",
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
    _emit_metric("ecb_fx_bronze", started)
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
def german_equity_proxy_silver(
    context,
    iceberg_catalog: IcebergCatalogResource,
    german_equity_proxy_bronze: dict[str, Any],
) -> str:
    _ = german_equity_proxy_bronze
    started = time.perf_counter()
    catalog = iceberg_catalog.get_catalog()
    result = dax_bronze_to_silver.run(catalog)
    context.add_output_metadata(
        _governed_asset_metadata(
            catalog,
            "german_equity_proxy_silver",
            {"table": result["table"], "row_count": _metadata_row_count(result)},
        )
    )
    _emit_metric("german_equity_proxy_silver", started)
    return str(result["table"])


@asset(group_name="silver")
def ecb_fx_silver(
    context,
    iceberg_catalog: IcebergCatalogResource,
    ecb_fx_bronze: dict[str, Any],
) -> str:
    _ = ecb_fx_bronze
    started = time.perf_counter()
    catalog = iceberg_catalog.get_catalog()
    result = ecb_fx_bronze_to_silver.run(catalog)
    context.add_output_metadata(
        _governed_asset_metadata(
            catalog,
            "ecb_fx_silver",
            {"table": result["table"], "row_count": _metadata_row_count(result)},
        )
    )
    _emit_metric("ecb_fx_silver", started)
    return str(result["table"])


@asset(group_name="gold")
def ecb_german_equity_proxy_features(
    context,
    iceberg_catalog: IcebergCatalogResource,
    ecb_silver: str,
    german_equity_proxy_silver: str,
) -> str:
    _ = (ecb_silver, german_equity_proxy_silver)
    started = time.perf_counter()
    catalog = iceberg_catalog.get_catalog()
    result = silver_to_gold_features.run(catalog)
    context.add_output_metadata(
        _governed_asset_metadata(
            catalog,
            "ecb_german_equity_proxy_features",
            {"table": result["table"], "event_count": _metadata_row_count(result)},
        )
    )
    _emit_metric("ecb_german_equity_proxy_features", started)
    return str(result["table"])


@asset(group_name="gold")
def eur_market_daily(
    context,
    iceberg_catalog: IcebergCatalogResource,
    ecb_silver: str,
    ecb_fx_silver: str,
    german_equity_proxy_silver: str,
) -> str:
    _ = (ecb_silver, ecb_fx_silver, german_equity_proxy_silver)
    started = time.perf_counter()
    catalog = iceberg_catalog.get_catalog()
    result = build_eur_market_daily.run(catalog)
    context.add_output_metadata(
        _governed_asset_metadata(
            catalog,
            "eur_market_daily",
            {"table": result["table"], "row_count": _metadata_row_count(result)},
        )
    )
    _emit_metric("eur_market_daily", started)
    return str(result["table"])


@asset(group_name="ml")
def ml_experiment(
    context,
    iceberg_catalog: IcebergCatalogResource,
    pipeline_config: PipelineConfigResource,
    ecb_german_equity_proxy_features: str,
) -> str:
    _ = ecb_german_equity_proxy_features
    started = time.perf_counter()
    catalog = iceberg_catalog.get_catalog()
    contract = contract_for_asset_key("ecb_german_equity_proxy_features")
    if contract is None:
        raise ValueError(
            "ecb_german_equity_proxy_features is not covered by a governed dataset contract"
        )
    location = contract.physical_location
    snapshot_id = iceberg_io.current_snapshot_id(catalog, location.namespace, location.table)
    lineage = build_ml_lineage_tuple(
        iceberg_snapshot_id=snapshot_id,
        dagster_run_id=context.run_id,
        feature_version=FEATURE_VERSION,
        data_contract_hash=contract_content_sha256(contract),
    )
    policy_hook = validate_ml_training_allowed(contract)
    experiment_result = run_experiment_set(
        catalog=catalog,
        mlflow_tracking_uri=pipeline_config.mlflow_tracking_uri,
        lineage=lineage,
        training_contract=contract,
    )
    context.add_output_metadata(
        {
            "best_run_id": experiment_result.best_run_id,
            "ml_lineage_sha256": lineage.sha256(),
            "policy_hook_sha256": policy_hook.sha256(),
            "model_evidence_path": experiment_result.model_evidence_path,
            "model_evidence_sha256": experiment_result.model_evidence_sha256,
            **lineage.model_dump(mode="json"),
        }
    )
    _emit_metric("ml_experiment", started)
    return experiment_result.best_run_id


@asset(group_name="catalog")
def openmetadata_trino_sync(
    context,
    ecb_german_equity_proxy_features: str,
) -> dict[str, Any]:
    """Refresh OpenMetadata's Trino catalog after Gold materializes."""
    _ = ecb_german_equity_proxy_features
    started = time.perf_counter()
    from governance.openmetadata_ingest import run_trino_metadata_ingest

    result = run_trino_metadata_ingest()
    context.add_output_metadata(
        {
            "status": result.get("status", "unknown"),
            "reason": result.get("reason", ""),
            "mode": result.get("mode", ""),
        }
    )
    if result.get("status") == "skipped":
        context.log.warning("openmetadata_trino_sync skipped: %s", result.get("reason"))
    elif result.get("status") == "ok":
        context.log.info("openmetadata_trino_sync completed via %s", result.get("mode"))
    else:
        context.log.warning("openmetadata_trino_sync unexpected result: %s", result)
    _emit_metric("openmetadata_trino_sync", started)
    return result


@sensor(
    job_name="demo_data_flow_job",
    minimum_interval_seconds=1800,
    default_status=DefaultSensorStatus.RUNNING,
)
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


@asset_check(
    asset=ecb_german_equity_proxy_features,
    description="ecb_german_equity_proxy_features should contain at least 10 rows",
)
def ecb_german_equity_proxy_features_min_rows_check(
    iceberg_catalog: IcebergCatalogResource,
    ecb_german_equity_proxy_features: str,
) -> AssetCheckResult:
    _ = ecb_german_equity_proxy_features
    catalog = iceberg_catalog.get_catalog()
    gold_df = iceberg_io.scan_table(catalog, "gold", "ecb_german_equity_proxy_features")
    row_count = int(len(gold_df.index))
    passed = row_count >= 10
    return AssetCheckResult(
        passed=passed,
        description=(
            "ecb_german_equity_proxy_features has enough event rows for event-study modeling"
            if passed
            else "ecb_german_equity_proxy_features has fewer than 10 rows"
        ),
        metadata={"row_count": row_count},
    )


def _staleness_check_for_asset(asset_key: str, table_df: pd.DataFrame) -> AssetCheckResult:
    contract = contract_for_asset_key(asset_key)
    if contract is None:
        return AssetCheckResult(
            passed=False,
            severity=AssetCheckSeverity.WARN,
            description=f"{asset_key}: no governed contract for staleness check",
        )
    passed, description, metadata = evaluate_max_staleness(table_df, contract)
    return AssetCheckResult(
        passed=passed,
        severity=AssetCheckSeverity.WARN,
        description=description,
        metadata=metadata,
    )


@asset_check(asset=ecb_bronze, description="ECB bronze freshness SLA (WARN)")
def ecb_bronze_staleness_check(
    iceberg_catalog: IcebergCatalogResource,
    ecb_bronze: dict[str, Any],
) -> AssetCheckResult:
    _ = ecb_bronze
    catalog = iceberg_catalog.get_catalog()
    return _staleness_check_for_asset(
        "ecb_bronze",
        iceberg_io.scan_table(catalog, "bronze", "ecb_rates"),
    )


@asset_check(asset=german_equity_proxy_bronze, description="EWG bronze freshness SLA (WARN)")
def german_equity_proxy_bronze_staleness_check(
    iceberg_catalog: IcebergCatalogResource,
    german_equity_proxy_bronze: dict[str, Any],
) -> AssetCheckResult:
    _ = german_equity_proxy_bronze
    catalog = iceberg_catalog.get_catalog()
    return _staleness_check_for_asset(
        "german_equity_proxy_bronze",
        iceberg_io.scan_table(catalog, "bronze", "german_equity_proxy_daily"),
    )


@asset_check(asset=ecb_silver, description="ECB silver freshness SLA (WARN)")
def ecb_silver_staleness_check(
    iceberg_catalog: IcebergCatalogResource,
    ecb_silver: str,
) -> AssetCheckResult:
    _ = ecb_silver
    catalog = iceberg_catalog.get_catalog()
    return _staleness_check_for_asset(
        "ecb_silver",
        iceberg_io.scan_table(catalog, "silver", "ecb_rates_cleaned"),
    )


@asset_check(
    asset=german_equity_proxy_silver,
    description="EWG silver freshness SLA (WARN)",
)
def german_equity_proxy_silver_staleness_check(
    iceberg_catalog: IcebergCatalogResource,
    german_equity_proxy_silver: str,
) -> AssetCheckResult:
    _ = german_equity_proxy_silver
    catalog = iceberg_catalog.get_catalog()
    return _staleness_check_for_asset(
        "german_equity_proxy_silver",
        iceberg_io.scan_table(catalog, "silver", "german_equity_proxy_daily_cleaned"),
    )


@asset_check(asset=ecb_fx_bronze, description="ECB FX bronze freshness SLA (WARN)")
def ecb_fx_bronze_staleness_check(
    iceberg_catalog: IcebergCatalogResource,
    ecb_fx_bronze: dict[str, Any],
) -> AssetCheckResult:
    _ = ecb_fx_bronze
    catalog = iceberg_catalog.get_catalog()
    return _staleness_check_for_asset(
        "ecb_fx_bronze",
        iceberg_io.scan_table(catalog, "bronze", "ecb_fx_rates"),
    )


@asset_check(asset=ecb_fx_silver, description="ECB FX silver freshness SLA (WARN)")
def ecb_fx_silver_staleness_check(
    iceberg_catalog: IcebergCatalogResource,
    ecb_fx_silver: str,
) -> AssetCheckResult:
    _ = ecb_fx_silver
    catalog = iceberg_catalog.get_catalog()
    return _staleness_check_for_asset(
        "ecb_fx_silver",
        iceberg_io.scan_table(catalog, "silver", "ecb_fx_rates_cleaned"),
    )


@asset_check(asset=eur_market_daily, description="EUR market daily freshness SLA (WARN)")
def eur_market_daily_staleness_check(
    iceberg_catalog: IcebergCatalogResource,
    eur_market_daily: str,
) -> AssetCheckResult:
    _ = eur_market_daily
    catalog = iceberg_catalog.get_catalog()
    return _staleness_check_for_asset(
        "eur_market_daily",
        iceberg_io.scan_table(catalog, "gold", "eur_market_daily"),
    )
