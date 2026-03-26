from __future__ import annotations

import os
import uuid
from io import BytesIO

import pandas as pd
import pytest
from minio import Minio


@pytest.fixture(scope="session")
def minio_client() -> Minio:
    endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    endpoint = endpoint.replace("http://", "").replace("https://", "").rstrip("/")
    access_key = os.environ.get("S3_ACCESS_KEY", os.environ.get("MINIO_ROOT_USER", "sololakehouse"))
    secret_key = os.environ.get(
        "S3_SECRET_KEY",
        os.environ.get("MINIO_ROOT_PASSWORD", "sololakehouse123"),
    )

    client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=False)
    try:
        client.list_buckets()
    except Exception as exc:
        pytest.skip(f"MinIO unreachable for integration tests: {exc}")
    return client


@pytest.fixture(scope="session")
def test_bucket(minio_client: Minio) -> str:
    bucket_name = f"sololakehouse-test-{uuid.uuid4().hex[:8]}"
    minio_client.make_bucket(bucket_name)
    try:
        yield bucket_name
    finally:
        for obj in minio_client.list_objects(bucket_name, recursive=True):
            minio_client.remove_object(bucket_name, obj.object_name)
        minio_client.remove_bucket(bucket_name)


def read_parquet_from_minio(minio_client: Minio, bucket: str, path: str) -> pd.DataFrame:
    response = minio_client.get_object(bucket, path)
    try:
        return pd.read_parquet(BytesIO(response.read()))
    finally:
        response.close()
        response.release_conn()
