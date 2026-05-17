#!/bin/sh
set -e

mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"

DATA_BUCKET="${DATA_BUCKET:-${BUCKET_NAME:-sololakehouse}}"
default_named_bucket() {
  base_bucket="$1"
  suffix="$2"
  case "${base_bucket}" in
    *-data) echo "${base_bucket%-data}-${suffix}" ;;
    *) echo "${base_bucket}-${suffix}" ;;
  esac
}

if [ "${DATA_BUCKET}" = "sololakehouse" ]; then
  DEFAULT_MLFLOW_ARTIFACT_BUCKET="mlflow-artifacts"
else
  DEFAULT_MLFLOW_ARTIFACT_BUCKET="$(default_named_bucket "${DATA_BUCKET}" "mlflow")"
fi

AUDIT_BUCKET="${AUDIT_BUCKET:-$(default_named_bucket "${DATA_BUCKET}" "audit")}"
MLFLOW_ARTIFACT_BUCKET="${MLFLOW_ARTIFACT_BUCKET:-${DEFAULT_MLFLOW_ARTIFACT_BUCKET}}"

mc mb --ignore-existing "local/${DATA_BUCKET}"
mc mb --ignore-existing "local/${AUDIT_BUCKET}"
mc mb --ignore-existing "local/${MLFLOW_ARTIFACT_BUCKET}"
echo "MinIO buckets initialized: ${DATA_BUCKET}, ${AUDIT_BUCKET}, ${MLFLOW_ARTIFACT_BUCKET}."
