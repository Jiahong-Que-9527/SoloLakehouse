#!/bin/sh
set -e

mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc mb --ignore-existing local/sololakehouse
mc mb --ignore-existing local/mlflow-artifacts
echo "MinIO buckets initialized."
