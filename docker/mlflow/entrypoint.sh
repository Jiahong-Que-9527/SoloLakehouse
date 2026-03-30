#!/bin/sh
set -eu

POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
MLFLOW_ARTIFACT_ROOT="${MLFLOW_ARTIFACT_ROOT:-s3://mlflow-artifacts/}"

BACKEND_STORE_URI="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/mlflow"

attempt=1
while [ "$attempt" -le 30 ]; do
  if mlflow db upgrade "${BACKEND_STORE_URI}"; then
    break
  fi
  if [ "$attempt" -eq 30 ]; then
    echo "mlflow db upgrade failed after 30 attempts"
    exit 1
  fi
  echo "mlflow db upgrade failed (attempt ${attempt}/30), retrying in 2s..."
  sleep 2
  attempt=$((attempt + 1))
done

exec mlflow server \
  --host 0.0.0.0 \
  --port 5000 \
  --backend-store-uri "${BACKEND_STORE_URI}" \
  --default-artifact-root "${MLFLOW_ARTIFACT_ROOT}"
