"""Dagster resources for SoloLakehouse v2.5 orchestration."""

from __future__ import annotations

import os

from minio import Minio

from dagster import ConfigurableResource
from storage_config import get_storage_config

DEFAULT_STORAGE_CONFIG = get_storage_config()


class MinioResource(ConfigurableResource):
    """Configurable MinIO client resource."""

    endpoint: str = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    access_key: str = os.environ.get(
        "S3_ACCESS_KEY", os.environ.get("MINIO_ROOT_USER", "sololakehouse")
    )
    secret_key: str = os.environ.get(
        "S3_SECRET_KEY", os.environ.get("MINIO_ROOT_PASSWORD", "sololakehouse123")
    )
    secure: bool = os.environ.get("MINIO_SECURE", "false").lower() == "true"

    def get_client(self) -> Minio:
        endpoint = self.endpoint.replace("http://", "").replace("https://", "").rstrip("/")
        return Minio(
            endpoint=endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
        )


class PipelineConfigResource(ConfigurableResource):
    """Pipeline runtime config resource."""

    bucket: str = DEFAULT_STORAGE_CONFIG.data_bucket
    audit_bucket: str = DEFAULT_STORAGE_CONFIG.audit_bucket
    mlflow_artifact_bucket: str = DEFAULT_STORAGE_CONFIG.mlflow_artifact_bucket
    mlflow_artifact_root: str = DEFAULT_STORAGE_CONFIG.mlflow_artifact_root
    warehouse_uri: str = DEFAULT_STORAGE_CONFIG.warehouse_uri
    mlflow_tracking_uri: str = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
    trino_url: str = os.environ.get("TRINO_URL", "http://localhost:8080")
