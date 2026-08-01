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
AUDIT_OBJECT_LOCK_MODE="${AUDIT_OBJECT_LOCK_MODE:-GOVERNANCE}"
AUDIT_OBJECT_LOCK_RETENTION="${AUDIT_OBJECT_LOCK_RETENTION:-2555d}"

mc mb --ignore-existing "local/${DATA_BUCKET}"
mc mb --ignore-existing "local/${MLFLOW_ARTIFACT_BUCKET}"

if mc stat "local/${AUDIT_BUCKET}" >/dev/null 2>&1; then
  audit_stat_json="$(mc stat --json "local/${AUDIT_BUCKET}" 2>/dev/null || true)"
  case "${audit_stat_json}" in
    *'"ObjectLock":{"enabled":"Enabled"'*) ;;
    *)
      echo "ERROR: ${AUDIT_BUCKET} exists without Object Lock enabled." >&2
      echo "Run 'make clean' and 'make up' to recreate the audit bucket with Object Lock." >&2
      exit 1
      ;;
  esac
else
  mc mb --with-lock "local/${AUDIT_BUCKET}"
  mc retention set --default "${AUDIT_OBJECT_LOCK_MODE}" "${AUDIT_OBJECT_LOCK_RETENTION}" "local/${AUDIT_BUCKET}"
fi

echo "MinIO buckets initialized: ${DATA_BUCKET}, ${AUDIT_BUCKET}, ${MLFLOW_ARTIFACT_BUCKET}."
echo "Audit bucket Object Lock: mode=${AUDIT_OBJECT_LOCK_MODE}, retention=${AUDIT_OBJECT_LOCK_RETENTION}."
