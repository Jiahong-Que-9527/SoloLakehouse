#!/bin/sh
set -e

mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"

DATA_BUCKET="${DATA_BUCKET:-${BUCKET_NAME:-sololakehouse}}"

mc mb --ignore-existing "local/${DATA_BUCKET}"
mc mb --ignore-existing local/mlflow-artifacts
echo "MinIO buckets initialized: ${DATA_BUCKET}, mlflow-artifacts."
