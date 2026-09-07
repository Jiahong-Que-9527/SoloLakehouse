#!/usr/bin/env bash
# Reset the bundled Airflow MySQL user to the Compose defaults expected by slh-openmetadata-ingestion.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ -f .env.secrets ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env.secrets
  set +a
fi

AIRFLOW_USER="${AIRFLOW_DB_USER:-airflow_user}"
AIRFLOW_PASSWORD="${AIRFLOW_DB_PASSWORD:-airflow_pass}"

if [[ -z "${OPENMETADATA_MYSQL_ROOT_PASSWORD:-}" ]]; then
  echo "OPENMETADATA_MYSQL_ROOT_PASSWORD is required (set in .env.secrets)" >&2
  exit 1
fi

echo "==> Resetting MySQL user ${AIRFLOW_USER} for airflow_db"
docker exec slh-om-mysql sh -lc \
  "mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -e \"ALTER USER '${AIRFLOW_USER}'@'%' IDENTIFIED BY '${AIRFLOW_PASSWORD}'; FLUSH PRIVILEGES;\""

echo "==> Restarting slh-openmetadata-ingestion"
docker restart slh-openmetadata-ingestion
sleep 5
docker ps --filter name=slh-openmetadata-ingestion --format '{{.Names}} {{.Status}}'
