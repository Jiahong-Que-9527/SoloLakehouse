#!/usr/bin/env bash
set -euo pipefail

create_admin_if_missing() {
  /app/.venv/bin/superset fab list-users | grep -q "${SUPERSET_ADMIN_USERNAME}"
}

ensure_database_connection() {
  local database_name="$1"
  local database_uri="$2"
  echo "Ensuring Superset database connection: ${database_name}"
  /app/.venv/bin/superset set-database-uri \
    --database_name "${database_name}" \
    --uri "${database_uri}"
}

echo "Running Superset metadata migrations..."
/app/.venv/bin/superset db upgrade

if ! create_admin_if_missing; then
  echo "Creating Superset admin user..."
  /app/.venv/bin/superset fab create-admin \
    --username "${SUPERSET_ADMIN_USERNAME}" \
    --firstname "${SUPERSET_ADMIN_FIRSTNAME:-Solo}" \
    --lastname "${SUPERSET_ADMIN_LASTNAME:-Lakehouse}" \
    --email "${SUPERSET_ADMIN_EMAIL}" \
    --password "${SUPERSET_ADMIN_PASSWORD}"
else
  echo "Superset admin user already exists."
fi

echo "Initializing Superset roles and permissions..."
/app/.venv/bin/superset init

ensure_database_connection \
  "${SUPERSET_TRINO_ICEBERG_DB_NAME:-trino_iceberg_gold}" \
  "${SUPERSET_TRINO_ICEBERG_URI:-trino://sololakehouse@trino:8080/iceberg/gold}"

ensure_database_connection \
  "${SUPERSET_TRINO_HIVE_DB_NAME:-trino_hive_default}" \
  "${SUPERSET_TRINO_HIVE_URI:-trino://sololakehouse@trino:8080/hive/default}"

echo "Starting Superset server..."
exec /app/docker/entrypoints/run-server.sh
