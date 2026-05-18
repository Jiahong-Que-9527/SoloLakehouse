# Entity Template Restore Drill - 2026-05-17

## Summary

Issue: #10

Result: PASS. OpenMetadata was classified as re-ingest-only for Phase 1.

The v2.5 local SoloLakehouse entity template was backed up from the local
reference runtime, restored into a disposable clone under `/tmp`, and validated
with service health checks, the demo data flow, and direct Trino Gold table
queries.

## Scope

| Item | Value |
|---|---|
| Product ID | `sololakehouse` |
| Runtime version | `slh-v2.5.1` |
| Source git SHA | `6d2e6571a90b1c89e876b25172710137657e861a` |
| Restore git SHA | `6d2e6571a90b1c89e876b25172710137657e861a` |
| Backup completed at | `2026-05-17T20:28:13Z` |
| Restore validated at | `2026-05-17T20:32:53Z` |
| Backup root | `/tmp/sololakehouse-backups/sololakehouse/restore-drill-20260517T202719Z` |
| Restore target | `/tmp/sololakehouse-restore-targets/restore-target-20260517T202927Z` |

The temporary backup and restore roots contained an `.env` snapshot and were
removed after the non-secret results below were transcribed.

## Restored State

| Component | Evidence |
|---|---|
| Entity `.env` | `files/env.snapshot` captured with mode `0600` |
| Object store | `sololakehouse`, `sololakehouse-audit`, and `mlflow-artifacts` restored |
| Object files | 36 object-store files listed in `metadata/object-store-files.txt` |
| PostgreSQL | `hive_metastore`, `mlflow`, `dagster_storage`, and `superset_metadata` dumps restored |
| Dagster local files | `files/dagster-data.tgz` restored |
| OpenMetadata | Service restored by clean re-initialization/re-index path; catalog history classified as re-ingest-only |
| Evidence manifest | 37 files listed in `metadata/final-evidence-manifest.txt` |

Resolved storage values:

```text
DATA_BUCKET=sololakehouse
AUDIT_BUCKET=sololakehouse-audit
MLFLOW_ARTIFACT_BUCKET=mlflow-artifacts
SUPERSET_DB_NAME=superset_metadata
```

## Validation

`make verify` passed after restore:

```text
MinIO            PASS    Buckets: mlflow-artifacts, sololakehouse, sololakehouse-audit
PostgreSQL       PASS    Databases: dagster_storage, hive_metastore, mlflow, superset_metadata
Hive Metastore   PASS    TCP port 9083 open
Trino            PASS    Running, not starting
MLflow           PASS    HTTP 200 /health
Dagster          PASS    HTTP 200 /server_info
Dagster S3 creds PASS    AWS + MLflow S3 credentials present
OpenMetadata     PASS    API OK (http://localhost:8585)
Superset         PASS    HTTP 200 (http://localhost:8088/health)
```

`make demo` passed after restore:

```text
Demo check      Rows  Status
--------------- ----- ------
Hive Gold       53    PASS
Iceberg Gold    53    PASS
```

Direct Trino row-count checks after restore:

| Query target | Rows |
|---|---:|
| `hive.gold.ecb_dax_features` | 53 |
| `iceberg.gold.ecb_dax_features_iceberg` | 53 |

All restored containers were healthy in `compose-ps-after-restore.txt`.

## Gaps Found

1. The runbook's `set -a; . "$ENV_FILE"; set +a` pattern is unsafe for the
   current `.env`, because Compose env files may contain unquoted spaces such
   as `SUPERSET_OAUTH_SCOPE=openid email profile`. The drill used
   `docker compose --env-file` plus explicit extraction of only the variables
   needed by shell commands.
2. The disposable clone did not contain a local `.venv`, so host-side make
   targets that run Python used the already prepared repository virtualenv:
   `/root/Workspace/My-Lakehouse/SoloLakehouse/.venv/bin/python`.
3. The OpenMetadata MySQL dump was captured, but direct restore failed on
   `apps_extension_time_series` SQL containing malformed `VALUES` syntax. The
   accepted Phase 1 strategy is re-ingest-only: rebuild/re-index OpenMetadata
   state instead of treating OpenMetadata MySQL continuity as a blocker.

## Acceptance Decision

Accepted for Phase 1 entity-template readiness:

- the restore target starts successfully;
- `make verify` passes;
- `make demo` passes;
- critical Hive and Iceberg Gold assets are queryable after restore;
- restore evidence and restore gaps are recorded here.

OpenMetadata catalog-history continuity is not required for Phase 1 entity
template readiness. A future entity that requires OpenMetadata history
preservation must validate a corrected dump/import strategy on a disposable
target before using restore/import as its acceptance path.

Follow-up issue: #21 classified the strategy.
