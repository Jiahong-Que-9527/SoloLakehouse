# Entity Backup and Restore Runbook

This runbook defines the minimum backup and restore procedure for a
SoloLakehouse-derived product entity before it is allowed to run continuously.

It applies to the v2.5 entity-template baseline and prepares the restore drill
tracked by issue #10.

## Status

- Applies to: v2.5 entity-template preparation.
- Related issue: #9.
- Depends on:
  - [Product Entity Contract](product-entity-contract.md)
  - [Entity Runtime State Layout](runtime-state-layout.md)
  - [Object Store Abstraction and MinIO Deferral](object-store-abstraction.md)
- Current provider: MinIO as the S3-compatible object store.

## Goals

The backup set must be enough to recreate one entity from:

1. code or release artifact,
2. entity `.env`,
3. object-store buckets,
4. PostgreSQL logical dumps,
5. OpenMetadata state or a documented re-ingestion path,
6. release and validation metadata.

Do not start a 24/7 FinLakehouse or Aviation Lakehouse runtime until this
runbook has been exercised once on a disposable restore target.

## State Inventory

| State | Current local path or service | Backup action | Restore preference |
|---|---|---|---|
| Code/release artifact | Git checkout under `app/` or repo root | Record git SHA, tag, and compose config | Re-clone or unpack release artifact |
| Entity `.env` | `.env` or `/opt/<product_id>/.env` | Copy as secret material | Copy to restore target and review every entity value |
| Data bucket | MinIO bucket `${DATA_BUCKET}` | `mc mirror` | Mirror back before service validation |
| Audit bucket | MinIO bucket `${AUDIT_BUCKET}` | `mc mirror` | Mirror back; v2.6+ must preserve immutability evidence |
| MLflow artifacts | MinIO bucket `${MLFLOW_ARTIFACT_BUCKET}` | `mc mirror` | Mirror back before MLflow validation |
| Hive Metastore DB | PostgreSQL `hive_metastore` | `pg_dump --format=custom` | Restore logical dump |
| MLflow DB | PostgreSQL `mlflow` | `pg_dump --format=custom` | Restore logical dump with artifacts bucket |
| Dagster DB | PostgreSQL `dagster_storage` | `pg_dump --format=custom` | Restore for run/event history when needed |
| Superset DB | PostgreSQL `${SUPERSET_DB_NAME:-superset_metadata}` | `pg_dump --format=custom` | Restore, then validate Trino connections |
| Dagster local files | `docker/data/dagster` or entity `data/dagster` | Archive directory | Restore for diagnostics/local instance data |
| OpenMetadata MySQL | `slh-om-mysql`, database `openmetadata_db` | Record re-ingestion strategy; optional `mysqldump` for diagnostics or history-preserving entities | Phase 1 default: start clean and re-ingest catalog metadata |
| OpenMetadata Elasticsearch | `docker/data/om-elasticsearch` | Rebuild/re-index; optional cold archive for fast local rollback only | Rebuild from OpenMetadata and Trino |
| Host logs | `/opt/<product_id>/logs` | Archive useful command logs | Restore only for evidence/debugging |

## Backup Root

Use one immutable timestamped backup root per backup attempt.

Local reference example:

```bash
export PRODUCT_ID="${PRODUCT_ID:-sololakehouse}"
export BACKUP_ID="$(date -u +%Y%m%dT%H%M%SZ)"
export BACKUP_ROOT="$HOME/sololakehouse-backups/${PRODUCT_ID}/${BACKUP_ID}"
mkdir -p "$BACKUP_ROOT"/{object-store,postgres,openmetadata,files,metadata,logs}
```

Do not stage local backups under `docker/data/`; `make clean` intentionally
removes that runtime directory.

Product entity example:

```bash
export PRODUCT_ID=finlakehouse
export BACKUP_ID="$(date -u +%Y%m%dT%H%M%SZ)"
export ENTITY_ROOT="/opt/${PRODUCT_ID}"
export APP_ROOT="${ENTITY_ROOT}/app"
export BACKUP_ROOT="${ENTITY_ROOT}/backup/${BACKUP_ID}"
mkdir -p "$BACKUP_ROOT"/{object-store,postgres,openmetadata,files,metadata,logs}
cd "$APP_ROOT"
```

For product entities, pass the product-level `.env` explicitly:

```bash
export ENV_FILE="${ENTITY_ROOT}/.env"
```

For the local reference stack, the default is:

```bash
export ENV_FILE="${ENV_FILE:-.env}"
```

The commands below use the full local Compose stack:

```bash
export COMPOSE_FILES="-f docker/docker-compose.yml -f docker/docker-compose.openmetadata.yml -f docker/docker-compose.superset.yml"
```

## Pre-Backup Checks

Run these before writing backup files:

```bash
git status --short --branch | tee "$BACKUP_ROOT/logs/git-status.txt"
git rev-parse HEAD | tee "$BACKUP_ROOT/metadata/git-sha.txt"
docker compose --env-file "$ENV_FILE" \
  $COMPOSE_FILES \
  ps | tee "$BACKUP_ROOT/logs/compose-ps-before-backup.txt"
ENV_FILE="$ENV_FILE" make verify | tee "$BACKUP_ROOT/logs/verify-before-backup.txt"
```

If `make verify` fails, either fix the runtime first or record the failure in
`$BACKUP_ROOT/metadata/backup-notes.md`. A backup from an unhealthy runtime can
still be useful, but it must not be treated as a clean restore baseline.

## Backup Procedure

### 1. Capture Entity Configuration

`.env` contains secrets. Store this backup root accordingly.

```bash
install -m 0600 "$ENV_FILE" "$BACKUP_ROOT/files/env.snapshot"
docker compose --env-file "$ENV_FILE" \
  $COMPOSE_FILES \
  config > "$BACKUP_ROOT/metadata/docker-compose.rendered.yml"
```

Capture the storage variables that define bucket ownership:

```bash
grep -E '^(PRODUCT_ID|ENVIRONMENT|RUNTIME_VERSION|DATA_BUCKET|AUDIT_BUCKET|MLFLOW_ARTIFACT_BUCKET|MLFLOW_ARTIFACT_ROOT|WAREHOUSE_URI)=' \
  "$ENV_FILE" > "$BACKUP_ROOT/metadata/entity-storage.env"
```

### 2. Mirror Object-Store Buckets

Resolve only the variables needed by shell commands. Do not blindly
`source`/`.` a Compose `.env` file; Compose env files may contain values with
spaces that are valid for Docker Compose but not valid shell assignment syntax.

```bash
env_value() {
  python3 - "$ENV_FILE" "$1" <<'PY'
import ast
import re
import sys

env_file, key = sys.argv[1], sys.argv[2]
value = ""
with open(env_file, encoding="utf-8") as handle:
    for raw_line in handle:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, raw_value = line.split("=", 1)
        if name != key:
            continue
        raw_value = raw_value.strip()
        if len(raw_value) >= 2 and raw_value[0] == raw_value[-1] and raw_value[0] in "'\"":
            try:
                value = ast.literal_eval(raw_value)
            except (SyntaxError, ValueError):
                value = raw_value[1:-1]
        else:
            value = re.sub(r"\s+#.*$", "", raw_value)
print(value)
PY
}

MINIO_ROOT_USER="$(env_value MINIO_ROOT_USER)"
MINIO_ROOT_PASSWORD="$(env_value MINIO_ROOT_PASSWORD)"
DATA_BUCKET="$(env_value DATA_BUCKET)"
BUCKET_NAME="$(env_value BUCKET_NAME)"
AUDIT_BUCKET="$(env_value AUDIT_BUCKET)"
MLFLOW_ARTIFACT_BUCKET="$(env_value MLFLOW_ARTIFACT_BUCKET)"

DATA_BUCKET="${DATA_BUCKET:-${BUCKET_NAME:-sololakehouse}}"
if [ "$DATA_BUCKET" = "sololakehouse" ]; then
  DEFAULT_MLFLOW_ARTIFACT_BUCKET="mlflow-artifacts"
else
  DEFAULT_MLFLOW_ARTIFACT_BUCKET="${DATA_BUCKET%-data}-mlflow"
fi
AUDIT_BUCKET="${AUDIT_BUCKET:-${DATA_BUCKET%-data}-audit}"
MLFLOW_ARTIFACT_BUCKET="${MLFLOW_ARTIFACT_BUCKET:-$DEFAULT_MLFLOW_ARTIFACT_BUCKET}"
```

Mirror data, audit, and MLflow artifact buckets. This command uses the existing
`minio/mc` image from the stack so the host does not need `mc` installed:

```bash
for bucket in "$DATA_BUCKET" "$AUDIT_BUCKET" "$MLFLOW_ARTIFACT_BUCKET"; do
  docker compose --env-file "$ENV_FILE" -f docker/docker-compose.yml run --rm \
    --no-deps \
    -v "$BACKUP_ROOT/object-store:/backup" \
    --entrypoint sh minio-init -c "
      mc alias set local http://minio:9000 \"$MINIO_ROOT_USER\" \"$MINIO_ROOT_PASSWORD\" &&
      mkdir -p \"/backup/${bucket}\" &&
      mc mirror --overwrite \"local/${bucket}\" \"/backup/${bucket}\"
    "
done
```

Write an object manifest:

```bash
find "$BACKUP_ROOT/object-store" -type f | sort \
  > "$BACKUP_ROOT/metadata/object-store-files.txt"
```

### 3. Dump PostgreSQL Databases

Dump each PostgreSQL database as a custom-format logical backup:

```bash
for db in hive_metastore mlflow dagster_storage "${SUPERSET_DB_NAME:-superset_metadata}"; do
  docker exec slh-postgres pg_dump \
    -U "$POSTGRES_USER" \
    --format=custom \
    --file="/tmp/${db}.dump" \
    "$db"
  docker cp "slh-postgres:/tmp/${db}.dump" "$BACKUP_ROOT/postgres/${db}.dump"
  docker exec slh-postgres rm -f "/tmp/${db}.dump"
done
```

Record database sizes for quick sanity checks:

```bash
docker exec slh-postgres psql -U "$POSTGRES_USER" -d postgres \
  -c "SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database ORDER BY datname;" \
  > "$BACKUP_ROOT/metadata/postgres-database-sizes.txt"
```

### 4. Capture Dagster Local Files

Most important Dagster state is in PostgreSQL, but local instance files are
useful for diagnostics:

```bash
tar -C docker/data -czf "$BACKUP_ROOT/files/dagster-data.tgz" dagster
```

For product entities that moved bind mounts to `/opt/<product_id>/data`, archive
from that entity data root instead:

```bash
tar -C "$ENTITY_ROOT/data" -czf "$BACKUP_ROOT/files/dagster-data.tgz" dagster
```

### 5. Back Up OpenMetadata

OpenMetadata has two state components:

- MySQL database `openmetadata_db`.
- Elasticsearch search index.

For the first entity split, OpenMetadata is classified as **re-ingest-only**.
Restore acceptance requires the service to start and catalog metadata to be
re-ingested from runtime sources such as Trino; it does not require preserving
OpenMetadata application history from MySQL.

Record that strategy in the backup set:

```bash
cat > "$BACKUP_ROOT/openmetadata/restore-strategy.md" <<'EOF'
OpenMetadata restore strategy: re-ingest-only for Phase 1.

The restore target starts OpenMetadata with clean MySQL and Elasticsearch state,
then re-ingests catalog metadata from runtime sources such as Trino after the
stack is healthy. OpenMetadata catalog-history continuity is not a Phase 1
restore acceptance requirement.
EOF
```

Optionally capture the MySQL database as diagnostic evidence or for entities
that explicitly require catalog-history continuity:

```bash
docker exec slh-om-mysql mysqldump \
  -uroot \
  -ppassword \
  --single-transaction \
  --routines \
  --triggers \
  openmetadata_db > "$BACKUP_ROOT/openmetadata/openmetadata_db.sql"
```

Do not rely on this optional dump for Phase 1 acceptance unless the
restore/import path has been validated on a disposable target for that entity.

For Elasticsearch, rebuild/re-index from OpenMetadata and Trino after restore.
If a fast local rollback archive is required, take a cold archive only after
stopping OpenMetadata services:

```bash
docker compose --env-file "$ENV_FILE" \
  $COMPOSE_FILES \
  stop openmetadata-server om-migrate om-elasticsearch
tar -C docker/data -czf "$BACKUP_ROOT/openmetadata/om-elasticsearch-data.tgz" om-elasticsearch
docker compose --env-file "$ENV_FILE" \
  $COMPOSE_FILES \
  up -d om-elasticsearch openmetadata-server
```

### 6. Finalize Backup Metadata

```bash
date -u +%Y-%m-%dT%H:%M:%SZ > "$BACKUP_ROOT/metadata/completed-at.txt"
find "$BACKUP_ROOT" -maxdepth 4 -type f -print | sort \
  > "$BACKUP_ROOT/metadata/backup-manifest.txt"
```

Minimum backup acceptance:

- `env.snapshot` exists and is protected as secret material.
- Object-store mirror contains `${DATA_BUCKET}`, `${AUDIT_BUCKET}`, and
  `${MLFLOW_ARTIFACT_BUCKET}`.
- PostgreSQL dumps exist for `hive_metastore`, `mlflow`, `dagster_storage`, and
  Superset.
- `openmetadata/restore-strategy.md` exists and classifies OpenMetadata as
  re-ingest-only or restore/import for the entity.
- `verify-before-backup.txt` records the pre-backup health state.

## Restore Procedure

Restore into a disposable target first. Never overwrite a running product entity
until the restore drill has passed and a cutover decision is recorded.

### 1. Prepare Restore Target

Create a clean runtime root:

```bash
export PRODUCT_ID=finlakehouse
export RESTORE_ROOT="/tmp/${PRODUCT_ID}-restore"
export BACKUP_ROOT="/opt/${PRODUCT_ID}/backup/<backup-id>"
mkdir -p "$RESTORE_ROOT"
git clone <repo-url> "$RESTORE_ROOT/app"
cd "$RESTORE_ROOT/app"
install -m 0600 "$BACKUP_ROOT/files/env.snapshot" .env
export ENV_FILE=".env"
export COMPOSE_FILES="-f docker/docker-compose.yml -f docker/docker-compose.openmetadata.yml -f docker/docker-compose.superset.yml"
```

For a product entity runtime root, you may keep the entity `.env` outside the
app directory, for example at `/opt/<product_id>/.env`. For a local disposable
clone, place the snapshot at `$RESTORE_ROOT/app/.env` so host-side verification
scripts that load the repository `.env` see the restored entity settings.

For a local disposable drill inside an existing repository checkout, use a new
clone or move the existing `docker/data/` aside before restoring.

### 2. Start Base Services

Start PostgreSQL and MinIO from the restored `ENV_FILE`. For local reference
restores where `.env` is in the app root, `scripts/bootstrap-postgres.py` loads
that file directly. For product restores that keep `.env` outside the app root,
export shell-compatible database settings explicitly before running
`make bootstrap-db`.

```bash
ENV_FILE="$ENV_FILE" make prepare-data-dirs
docker compose --env-file "$ENV_FILE" \
  -f docker/docker-compose.yml \
  up -d postgres minio
ENV_FILE="$ENV_FILE" make wait-postgres-ready
ENV_FILE="$ENV_FILE" make bootstrap-db
```

### 3. Restore Object-Store Buckets

If this step is run from a new shell, re-run the variable-resolution snippet
from the backup section so `DATA_BUCKET`, `AUDIT_BUCKET`,
`MLFLOW_ARTIFACT_BUCKET`, `MINIO_ROOT_USER`, and `MINIO_ROOT_PASSWORD` are set.

Create expected buckets, then mirror object data back:

```bash
docker compose --env-file "$ENV_FILE" -f docker/docker-compose.yml up minio-init

for bucket in "$DATA_BUCKET" "$AUDIT_BUCKET" "$MLFLOW_ARTIFACT_BUCKET"; do
  docker compose --env-file "$ENV_FILE" -f docker/docker-compose.yml run --rm \
    --no-deps \
    -v "$BACKUP_ROOT/object-store:/backup" \
    --entrypoint sh minio-init -c "
      mc alias set local http://minio:9000 \"$MINIO_ROOT_USER\" \"$MINIO_ROOT_PASSWORD\" &&
      if [ ! -d \"/backup/${bucket}\" ]; then
        echo \"Missing object-store backup source: /backup/${bucket}\" >&2
        exit 1
      fi &&
      mc mirror --overwrite \"/backup/${bucket}\" \"local/${bucket}\"
    "
done
```

### 4. Restore PostgreSQL Dumps

Stop services that depend on PostgreSQL before restoring:

```bash
docker compose --env-file "$ENV_FILE" \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.superset.yml \
  stop hive-metastore mlflow dagster-webserver dagster-daemon superset || true
```

Restore logical dumps:

```bash
for db in hive_metastore mlflow dagster_storage "${SUPERSET_DB_NAME:-superset_metadata}"; do
  docker exec slh-postgres psql -U "$POSTGRES_USER" -d postgres \
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${db}' AND pid <> pg_backend_pid();"
  docker exec slh-postgres dropdb -U "$POSTGRES_USER" --if-exists "$db"
  docker exec slh-postgres createdb -U "$POSTGRES_USER" "$db"
  docker cp "$BACKUP_ROOT/postgres/${db}.dump" "slh-postgres:/tmp/${db}.dump"
  docker exec slh-postgres pg_restore \
    -U "$POSTGRES_USER" \
    --dbname="$db" \
    --no-owner \
    "/tmp/${db}.dump"
  docker exec slh-postgres rm -f "/tmp/${db}.dump"
done
```

### 5. Restore OpenMetadata

For Phase 1, use the re-ingest-only strategy recorded in
`$BACKUP_ROOT/openmetadata/restore-strategy.md`. Start OpenMetadata with clean
MySQL and Elasticsearch state, then re-ingest catalog metadata from runtime
sources such as Trino after the stack is healthy:

```bash
docker compose --env-file "$ENV_FILE" \
  $COMPOSE_FILES \
  up -d om-mysql om-elasticsearch om-migrate openmetadata-server
```

After `ENV_FILE="$ENV_FILE" make verify` passes, re-create or re-run the
OpenMetadata ingestion workflow for the restored entity. Record the ingestion
run, service names, and any manually configured catalog settings in the restore
evidence.

Only restore OpenMetadata MySQL when catalog-history continuity is an explicit
entity requirement and the dump/import process has already been validated on a
disposable target:

```bash
docker compose --env-file "$ENV_FILE" \
  $COMPOSE_FILES \
  up -d om-mysql om-elasticsearch

cat "$BACKUP_ROOT/openmetadata/openmetadata_db.sql" | \
  docker exec -i slh-om-mysql mysql -uroot -ppassword openmetadata_db
```

If restoring the optional cold Elasticsearch archive:

```bash
docker compose --env-file "$ENV_FILE" \
  $COMPOSE_FILES \
  stop om-elasticsearch openmetadata-server || true
rm -rf docker/data/om-elasticsearch
tar -C docker/data -xzf "$BACKUP_ROOT/openmetadata/om-elasticsearch-data.tgz"
```

If a history-preserving MySQL restore fails in a disposable drill, reset the
target's OpenMetadata MySQL and Elasticsearch data directories, return to the
re-ingest-only path, and record catalog-history continuity as a restore gap. Do
not let OpenMetadata catalog-history continuity block Phase 1 restore acceptance
unless it is an explicit requirement for that entity.

### 6. Restore Dagster Local Files

```bash
tar -C docker/data -xzf "$BACKUP_ROOT/files/dagster-data.tgz"
```

For product entity roots, extract into `$ENTITY_ROOT/data`.

### 7. Start Full Stack

```bash
ENV_FILE="$ENV_FILE" make up
```

## Post-Restore Validation

A restore is not accepted until these checks are recorded:

```bash
ENV_FILE="$ENV_FILE" make verify | tee "$BACKUP_ROOT/logs/verify-after-restore.txt"
ENV_FILE="$ENV_FILE" make demo | tee "$BACKUP_ROOT/logs/demo-after-restore.txt"
```

Minimum data checks:

```bash
docker compose --env-file "$ENV_FILE" -f docker/docker-compose.yml exec -T trino \
  trino --server http://localhost:8080 --user "${TRINO_USER:-sololakehouse}" \
  --execute "SELECT count(*) FROM hive.gold.ecb_dax_features"

docker compose --env-file "$ENV_FILE" -f docker/docker-compose.yml exec -T trino \
  trino --server http://localhost:8080 --user "${TRINO_USER:-sololakehouse}" \
  --execute "SELECT count(*) FROM iceberg.gold.ecb_dax_features_iceberg"
```

Minimum service checks:

- MinIO contains data, audit, and MLflow artifact buckets.
- PostgreSQL contains `hive_metastore`, `mlflow`, `dagster_storage`, and
  Superset metadata databases.
- Hive Metastore starts and Trino can query Hive and Iceberg Gold.
- MLflow UI opens and previous runs/artifacts are visible when restored.
- Dagster UI opens and restored run history is visible if `dagster_storage` was
  restored.
- Superset opens and Trino database connections are valid.
- OpenMetadata opens; either restored catalog history is visible or re-ingestion
  has been completed and recorded.

Record restore evidence:

```bash
date -u +%Y-%m-%dT%H:%M:%SZ > "$BACKUP_ROOT/metadata/restore-validated-at.txt"
git rev-parse HEAD > "$BACKUP_ROOT/metadata/restore-git-sha.txt"
```

## Failure Handling

If restore validation fails:

1. Keep the failed restore target intact for inspection.
2. Record failing command output under `$BACKUP_ROOT/logs/`.
3. Classify the failure as object-store, PostgreSQL, OpenMetadata, Superset,
   orchestration, or data validation.
4. Open a follow-up issue linked to #10 if the restore drill uncovers a real
   gap.

Do not promote the entity template to Phase 2 until the restore drill passes or
the remaining gaps are explicitly accepted.
