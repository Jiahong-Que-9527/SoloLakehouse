"""Dagster resources for SoloLakehouse v2.5 orchestration."""

from __future__ import annotations

import os

from minio import Minio

from dagster import ConfigurableResource


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

    bucket: str = os.environ.get("BUCKET_NAME", "sololakehouse")
    mlflow_tracking_uri: str = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
    trino_url: str = os.environ.get("TRINO_URL", "http://localhost:8080")
