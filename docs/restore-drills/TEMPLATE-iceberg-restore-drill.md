# Restore Drill Template — Iceberg Baseline (v2.5.x+)

Copy this file to `docs/restore-drills/YYYY-MM-DD-<entity>-iceberg-restore-drill.md`
and fill in every field during the drill. The completed record is the drill
evidence required by `docs/entity-backup-restore-runbook.md`.

**When to run this drill:**
- Before starting any 24/7 entity deployment (FinLakehouse, Aviation Lakehouse).
- After any major infrastructure change (object-store migration, Iceberg
  namespace re-bootstrap, Postgres major version upgrade).
- At least once per 90 days for continuously operated entities.

The 2026-05-17 drill used the Parquet-era v2.5.1 baseline. This template covers
the Iceberg-native baseline introduced in v2.5.x (ADR-020). Key differences:
- Hive Metastore state is now essential: it holds all Bronze, Silver, and Gold
  Iceberg table metadata. Restoring only MinIO buckets is insufficient.
- `make demo` now checks `iceberg.gold.ecb_dax_features` (not `hive.gold.*`
  or `iceberg.gold.ecb_dax_features_iceberg`).

---

## Summary

| Field | Value |
|---|---|
| Result | PASS / FAIL |
| Date | YYYY-MM-DD |
| Issue / ticket | #XX |
| Notes | |

---

## Scope

| Item | Value |
|---|---|
| Product ID | |
| Runtime version | slh-v2.5.x (ADR-020 Iceberg baseline) |
| Source git SHA | |
| Restore git SHA | |
| Backup completed at | |
| Restore validated at | |
| Backup root | |
| Restore target | |

---

## Backup checklist

- [ ] MinIO bucket snapshot: `DATA_BUCKET` (includes `warehouse/` Iceberg files)
- [ ] MinIO bucket snapshot: `AUDIT_BUCKET`
- [ ] MinIO bucket snapshot: `MLFLOW_ARTIFACT_BUCKET`
- [ ] PostgreSQL dump: `hive_metastore` database
- [ ] PostgreSQL dump: `mlflow` database
- [ ] PostgreSQL dump: `dagster_storage` database
- [ ] PostgreSQL dump: `superset_metadata` database
- [ ] `.env` snapshot captured (mode 0600, stored separately from backup root)
- [ ] Git SHA and runtime version recorded

---

## Restore steps

```bash
# 1. Provision fresh target host / directory
#    Replace <restore-root> with a temp path (e.g. /tmp/flh-restore-YYYYMMDD)

export RESTORE_ROOT=<restore-root>
mkdir -p "$RESTORE_ROOT"/{app,data,backup,logs}

# 2. Clone repo at the recorded restore SHA
git clone https://github.com/Jiahong-Que-9527/SoloLakehouse.git "$RESTORE_ROOT/app"
cd "$RESTORE_ROOT/app"
git checkout <restore-git-sha>

# 3. Place .env
cp <env-snapshot-path> "$RESTORE_ROOT/.env"
chmod 600 "$RESTORE_ROOT/.env"
ln -sfn "$RESTORE_ROOT/data" "$RESTORE_ROOT/app/docker/data"

# 4. Restore object store
# (use mc mirror or aws s3 sync from backup to buckets after starting MinIO)
ENV_FILE="$RESTORE_ROOT/.env" make up
# Wait for MinIO to be ready, then:
# mc mirror <backup>/DATA_BUCKET  myminio/<DATA_BUCKET>
# mc mirror <backup>/AUDIT_BUCKET  myminio/<AUDIT_BUCKET>
# mc mirror <backup>/MLFLOW_BUCKET myminio/<MLFLOW_ARTIFACT_BUCKET>

# 5. Restore PostgreSQL
# docker exec -i <postgres-container> psql -U postgres < hive_metastore.dump
# docker exec -i <postgres-container> psql -U postgres < mlflow.dump
# docker exec -i <postgres-container> psql -U postgres < dagster_storage.dump
# docker exec -i <postgres-container> psql -U postgres < superset_metadata.dump

# 6. Re-initialise Iceberg namespaces (idempotent — safe to run on restored state)
ENV_FILE="$RESTORE_ROOT/.env" make init-iceberg

# 7. Verify
ENV_FILE="$RESTORE_ROOT/.env" make verify

# 8. Run demo acceptance check
ENV_FILE="$RESTORE_ROOT/.env" make demo

# 9. Manual Trino queries
docker compose --env-file "$RESTORE_ROOT/.env" -f docker/docker-compose.yml exec -T trino \
  trino --server http://localhost:8080 --user finlakehouse \
  --execute "SELECT count(*) FROM iceberg.gold.ecb_dax_features"

docker compose --env-file "$RESTORE_ROOT/.env" -f docker/docker-compose.yml exec -T trino \
  trino --server http://localhost:8080 --user finlakehouse \
  --execute "SELECT count(*) FROM iceberg.bronze.ecb_rates"
```

---

## Restored state evidence

| Component | Evidence |
|---|---|
| Entity `.env` | |
| Object store — DATA_BUCKET | |
| Object store — AUDIT_BUCKET | |
| Object store — MLFLOW_ARTIFACT_BUCKET | |
| PostgreSQL — hive_metastore | |
| PostgreSQL — mlflow | |
| PostgreSQL — dagster_storage | |
| PostgreSQL — superset_metadata | |
| Iceberg namespace init | |

---

## Validation results

| Check | Result | Notes |
|---|---|---|
| `make verify` exit 0 | | |
| `make demo` exit 0 | | |
| `iceberg.gold.ecb_dax_features` row count > 0 | | |
| `iceberg.bronze.ecb_rates` row count > 0 | | |
| MLflow run visible | | |
| Dagster run history visible | | |
| OpenMetadata re-ingest completed | | |

---

## Acceptance criteria

- All required validation checks pass.
- `iceberg.gold.ecb_dax_features` and `iceberg.bronze.ecb_rates` return rows.
- Drill result recorded as PASS in this document before the entity is declared
  live for 24/7 operation.
