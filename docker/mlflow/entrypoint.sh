#!/bin/sh
set -eu

POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
MLFLOW_ARTIFACT_ROOT="${MLFLOW_ARTIFACT_ROOT:-s3://mlflow-artifacts/}"

BACKEND_STORE_URI="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/mlflow"

# Drop all public tables in the mlflow database so a full re-migration can run.
# Called when repeated mlflow db upgrade failures indicate stale Alembic state
# (e.g. alembic_version has entries from a prior partial run, but base tables
# like "metrics" were never actually created).
reset_mlflow_schema() {
  echo "mlflow db upgrade failed repeatedly; resetting database schema to recover from stale migration state..."
  python3 << 'PYEOF'
import os
import psycopg2

conn = psycopg2.connect(
    host=os.environ.get("POSTGRES_HOST", "postgres"),
    port=int(os.environ.get("POSTGRES_PORT", "5432")),
    user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
    dbname="mlflow",
)
conn.autocommit = True
with conn.cursor() as cur:
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    tables = [row[0] for row in cur.fetchall()]
    for table in tables:
        cur.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
        print(f"Dropped: {table}")
conn.close()
print("Schema reset complete; will retry mlflow db upgrade from scratch.")
PYEOF
}

attempt=1
while [ "$attempt" -le 30 ]; do
  if mlflow db upgrade "${BACKEND_STORE_URI}"; then
    break
  fi
  if [ "$attempt" -eq 30 ]; then
    echo "mlflow db upgrade failed after 30 attempts"
    exit 1
  fi
  # After 5 consecutive failures, the error is likely a stale alembic_version
  # table (from a previous partial run) rather than a transient connection issue.
  # Drop all tables so the next attempt runs a clean full migration.
  if [ "$attempt" -eq 5 ]; then
    reset_mlflow_schema || true
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
