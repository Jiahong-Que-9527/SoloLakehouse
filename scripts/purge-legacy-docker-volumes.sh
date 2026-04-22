#!/usr/bin/env sh
# Remove obsolete *named* Docker volumes from the pre-bind-mount layout.
# Safe to run after `docker compose down`: removes typical project-prefixed volume names
# plus any dangling volumes matching the old SoloLakehouse suffixes.
set -eu
ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
base=$(basename "$ROOT")
lc=$(printf '%s' "$base" | tr '[:upper:]' '[:lower:]')

for prefix in "$lc" "$base" docker Docker; do
  for suffix in minio_data postgres_data dagster_storage om_mysql_data om_es_data; do
    if docker volume rm "${prefix}_${suffix}" >/dev/null 2>&1; then
      echo "Removed volume: ${prefix}_${suffix}"
    fi
  done
done

for v in $(docker volume ls -q -f dangling=true 2>/dev/null); do
  case "$v" in
    *_minio_data|*_postgres_data|*_dagster_storage|*_om_mysql_data|*_om_es_data)
      if docker volume rm "$v" >/dev/null 2>&1; then
        echo "Removed dangling volume: $v"
      fi
      ;;
  esac
done
