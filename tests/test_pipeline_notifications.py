from __future__ import annotations

import sys
from pathlib import Path

DAGSTER_DIR = Path(__file__).resolve().parent.parent / "dagster"
if str(DAGSTER_DIR) not in sys.path:
    sys.path.insert(0, str(DAGSTER_DIR))

from pipeline_notifications import (  # noqa: E402
    AssetMaterializationSummary,
    PipelineRunSummary,
    TableSummary,
    build_pipeline_run_email,
    format_pipeline_run_email_body,
    materializations_from_run,
    notification_config_from_environ,
    parse_recipient_addresses,
)


def test_notification_config_requires_recipient_and_host() -> None:
    assert notification_config_from_environ({}) is None
    assert (
        notification_config_from_environ({"PIPELINE_NOTIFY_EMAIL_TO": "ops@example.com"}) is None
    )
    config = notification_config_from_environ(
        {
            "PIPELINE_NOTIFY_EMAIL_TO": "ops@example.com, alerts@example.com",
            "SMTP_HOST": "smtp.example.com",
            "SMTP_USER": "bot@example.com",
            "SMTP_PASSWORD": "secret",
        }
    )
    assert config is not None
    assert config.to_addresses == ("ops@example.com", "alerts@example.com")
    assert config.smtp_host == "smtp.example.com"
    assert config.from_address == "bot@example.com"
    assert config.use_tls is True


def test_parse_recipient_addresses() -> None:
    assert parse_recipient_addresses("a@example.com, b@example.com") == (
        "a@example.com",
        "b@example.com",
    )


def test_build_pipeline_run_email_includes_run_link() -> None:
    message = build_pipeline_run_email(
        job_name="demo_data_flow_job",
        run_id="run-123",
        status_label="SUCCESS",
        dagster_url="http://localhost:3000",
    )
    body = message.get_content()
    assert "demo_data_flow_job" in body
    assert "run-123" in body
    assert "http://localhost:3000/runs/run-123" in body


def test_format_pipeline_run_email_body_includes_assets_and_tables() -> None:
    body = format_pipeline_run_email_body(
        PipelineRunSummary(
            job_name="demo_data_flow_job",
            run_id="run-123",
            status_label="SUCCESS",
            dagster_url="http://localhost:3000",
            start_time="2026-09-04T14:00:00+00:00",
            end_time="2026-09-04T14:05:00+00:00",
            materializations=(
                AssetMaterializationSummary(
                    asset_key="ecb_bronze",
                    metadata={"valid_count": "12", "iceberg_snapshot_id": "snap-1"},
                ),
            ),
            table_summaries=(
                TableSummary(
                    qualified_name="iceberg.gold.ecb_german_equity_proxy_features",
                    row_count=62,
                    min_date="2015-01-15",
                    max_date="2026-09-03",
                ),
            ),
        )
    )
    assert "ecb_bronze" in body
    assert "valid_count: 12" in body
    assert "iceberg.gold.ecb_german_equity_proxy_features" in body
    assert "rows: 62" in body
    assert "2015-01-15" in body


def test_materializations_from_run() -> None:
    summaries = materializations_from_run(
        {
            "assetMaterializations": [
                {
                    "assetKey": {"path": ["ecb_bronze"]},
                    "metadataEntries": [
                        {"label": "valid_count", "intValue": 10},
                        {"label": "status", "text": "ok"},
                    ],
                }
            ]
        }
    )
    assert len(summaries) == 1
    assert summaries[0].asset_key == "ecb_bronze"
    assert summaries[0].metadata["valid_count"] == "10"
    assert summaries[0].metadata["status"] == "ok"
