from __future__ import annotations

from storage_config import get_data_bucket, get_storage_config, get_warehouse_uri


def test_storage_config_defaults_to_v25_reference_values() -> None:
    config = get_storage_config({})

    assert config.data_bucket == "sololakehouse"
    assert config.warehouse_uri == "s3a://sololakehouse/warehouse/"


def test_data_bucket_takes_precedence_over_legacy_bucket_name() -> None:
    config = get_storage_config(
        {
            "DATA_BUCKET": "finlakehouse-data",
            "BUCKET_NAME": "legacy-bucket",
        }
    )

    assert config.data_bucket == "finlakehouse-data"
    assert config.warehouse_uri == "s3a://finlakehouse-data/warehouse/"


def test_legacy_bucket_name_remains_supported() -> None:
    assert get_data_bucket({"BUCKET_NAME": "legacy-bucket"}) == "legacy-bucket"
    assert get_warehouse_uri({"BUCKET_NAME": "legacy-bucket"}) == (
        "s3a://legacy-bucket/warehouse/"
    )


def test_explicit_warehouse_uri_is_normalized() -> None:
    config = get_storage_config(
        {
            "DATA_BUCKET": "aviation-lakehouse-data",
            "WAREHOUSE_URI": "s3a://aviation-lakehouse-data/custom-warehouse",
        }
    )

    assert config.warehouse_uri == "s3a://aviation-lakehouse-data/custom-warehouse/"
