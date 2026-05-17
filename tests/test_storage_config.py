from __future__ import annotations

from storage_config import (
    get_audit_bucket,
    get_data_bucket,
    get_mlflow_artifact_bucket,
    get_mlflow_artifact_root,
    get_storage_config,
    get_warehouse_uri,
)


def test_storage_config_defaults_to_v25_reference_values() -> None:
    config = get_storage_config({})

    assert config.data_bucket == "sololakehouse"
    assert config.audit_bucket == "sololakehouse-audit"
    assert config.mlflow_artifact_bucket == "mlflow-artifacts"
    assert config.mlflow_artifact_root == "s3://mlflow-artifacts/"
    assert config.warehouse_uri == "s3a://sololakehouse/warehouse/"


def test_data_bucket_takes_precedence_over_legacy_bucket_name() -> None:
    config = get_storage_config(
        {
            "DATA_BUCKET": "finlakehouse-data",
            "BUCKET_NAME": "legacy-bucket",
        }
    )

    assert config.data_bucket == "finlakehouse-data"
    assert config.audit_bucket == "finlakehouse-audit"
    assert config.mlflow_artifact_bucket == "finlakehouse-mlflow"
    assert config.mlflow_artifact_root == "s3://finlakehouse-mlflow/"
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


def test_explicit_mlflow_and_audit_storage_are_supported() -> None:
    config = get_storage_config(
        {
            "DATA_BUCKET": "aviation-lakehouse-data",
            "AUDIT_BUCKET": "aviation-evidence",
            "MLFLOW_ARTIFACT_BUCKET": "aviation-runs",
            "MLFLOW_ARTIFACT_ROOT": "s3://aviation-runs/custom-root",
        }
    )

    assert config.audit_bucket == "aviation-evidence"
    assert config.mlflow_artifact_bucket == "aviation-runs"
    assert config.mlflow_artifact_root == "s3://aviation-runs/custom-root/"


def test_storage_accessors_return_entity_bucket_values() -> None:
    env = {"DATA_BUCKET": "finlakehouse-data"}

    assert get_audit_bucket(env) == "finlakehouse-audit"
    assert get_mlflow_artifact_bucket(env) == "finlakehouse-mlflow"
    assert get_mlflow_artifact_root(env) == "s3://finlakehouse-mlflow/"
