#!/usr/bin/env sh
# Create bind-mount directories under docker/data/ with permissions suitable for local Compose.
set -eu
ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p \
  docker/data/minio \
  docker/data/postgres \
  docker/data/dagster \
  docker/data/om-mysql \
  docker/data/om-elasticsearch

# PostgreSQL official image init expects to own PGDATA; keep private (entrypoint will chown).
chmod 700 docker/data/postgres 2>/dev/null || true

# MinIO / Dagster / OM MySQL / ES: permissive for mixed container UIDs in local dev.
chmod 777 docker/data/minio docker/data/dagster docker/data/om-mysql docker/data/om-elasticsearch 2>/dev/null || true
