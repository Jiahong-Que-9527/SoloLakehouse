"""Dagster Definitions for SoloLakehouse v2."""

from __future__ import annotations

import os
import sys

from dagster import AssetSelection, Definitions, ScheduleDefinition, define_asset_job

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

from assets import (  # noqa: E402
    dax_bronze,
    dax_silver,
    ecb_data_freshness_sensor,
    ecb_bronze,
    ecb_silver,
    gold_features,
    gold_features_min_rows_check,
    ml_experiment,
)
from io_managers import ParquetIOManager  # noqa: E402
from resources import MinioResource, PipelineConfigResource  # noqa: E402

all_assets = [ecb_bronze, dax_bronze, ecb_silver, dax_silver, gold_features, ml_experiment]

full_pipeline_job = define_asset_job(
    name="full_pipeline_job",
    selection=AssetSelection.assets(*all_assets),
)

daily_pipeline_schedule = ScheduleDefinition(
    name="daily_pipeline_schedule",
    job=full_pipeline_job,
    cron_schedule="0 6 * * 1-5",
    execution_timezone="UTC",
)

defs = Definitions(
    assets=all_assets,
    asset_checks=[gold_features_min_rows_check],
    jobs=[full_pipeline_job],
    schedules=[daily_pipeline_schedule],
    sensors=[ecb_data_freshness_sensor],
    resources={
        "minio": MinioResource(),
        "pipeline_config": PipelineConfigResource(),
        # Optional IO manager for DataFrame-native asset experiments.
        "parquet_io_manager": ParquetIOManager(),
    },
)
