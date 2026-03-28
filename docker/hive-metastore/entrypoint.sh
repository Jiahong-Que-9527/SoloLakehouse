#!/bin/bash
set -euo pipefail

envsubst < /opt/hive/conf/metastore-site.xml.template > /opt/hive/conf/metastore-site.xml

DB_HOST="${DB_HOST:-postgres}"
DB_USER="${DB_USER:-postgres}"
DB_PASS="${DB_PASS:-postgres}"
export PGPASSWORD="${DB_PASS}"

psql_base=(psql -h "${DB_HOST}" -U "${DB_USER}" -d hive_metastore -Atq)

ctlgs_exists="$("${psql_base[@]}" -c "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'CTLGS';" || true)"

if [ "${ctlgs_exists}" != "1" ]; then
  table_count="$("${psql_base[@]}" -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" || true)"
  if [ -n "${table_count}" ] && [ "${table_count}" != "0" ]; then
    echo "Hive metastore schema is incomplete; resetting public schema before re-init."
    "${psql_base[@]}" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
  fi
  schematool -dbType postgres -initSchemaTo 4.0.0
fi

exec hive --service metastore
