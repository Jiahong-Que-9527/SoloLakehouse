#!/bin/sh
set -eu

POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
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

MLFLOW_ARTIFACT_BUCKET="${MLFLOW_ARTIFACT_BUCKET:-${DEFAULT_MLFLOW_ARTIFACT_BUCKET}}"
MLFLOW_ARTIFACT_ROOT="${MLFLOW_ARTIFACT_ROOT:-s3://${MLFLOW_ARTIFACT_BUCKET}/}"
case "${MLFLOW_ARTIFACT_ROOT}" in
  */) ;;
  *) MLFLOW_ARTIFACT_ROOT="${MLFLOW_ARTIFACT_ROOT}/" ;;
esac
MLFLOW_ALLOWED_HOSTS="${MLFLOW_ALLOWED_HOSTS:-localhost,localhost:5000,127.0.0.1,127.0.0.1:5000,mlflow,mlflow:5000}"

BACKEND_STORE_URI="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/mlflow"

# Wait until PostgreSQL accepts connections before starting MLflow.
# Avoid calling `mlflow db upgrade` directly: on an empty DB it can fail with
# migrations that assume base tables already exist.
wait_for_postgres() {
  attempt=1
  max_attempts=30
  sleep_seconds=2

  echo "Waiting for PostgreSQL at ${POSTGRES_HOST}:${POSTGRES_PORT}..."
  while [ "$attempt" -le "$max_attempts" ]; do
    if python3 << 'PYEOF'
import os
import psycopg2

conn = psycopg2.connect(
    host=os.environ.get("POSTGRES_HOST", "postgres"),
    port=int(os.environ.get("POSTGRES_PORT", "5432")),
    user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
    dbname="mlflow",
    connect_timeout=3,
)
conn.close()
PYEOF
    then
      echo "PostgreSQL is ready."
      return 0
    fi
    if [ "$attempt" -eq "$max_attempts" ]; then
      echo "PostgreSQL did not become ready after ${max_attempts} attempts"
      return 1
    fi
    echo "PostgreSQL not ready (attempt ${attempt}/${max_attempts}), retrying in ${sleep_seconds}s..."
    sleep "$sleep_seconds"
    attempt=$((attempt + 1))
  done
}

wait_for_postgres

exec mlflow server \
  --host 0.0.0.0 \
  --port 5000 \
  --allowed-hosts "${MLFLOW_ALLOWED_HOSTS}" \
  --backend-store-uri "${BACKEND_STORE_URI}" \
  --default-artifact-root "${MLFLOW_ARTIFACT_ROOT}"
