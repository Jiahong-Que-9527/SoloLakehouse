# Operational SLO Evidence (v2.9 Block C)

v2.9 evaluates a minimal SLO set from existing runtime health checks. This is
**not** the v3 Prometheus/Grafana stack (ADR-015); it reuses `make verify`.

## SLO scope

Each default SLO maps one-to-one to a verify-setup service:

| SLO ID | Service |
|---|---|
| `platform.minio.availability` | MinIO |
| `platform.postgres.availability` | PostgreSQL |
| `platform.hive_metastore.availability` | Hive Metastore |
| `platform.trino.availability` | Trino |
| `platform.mlflow.availability` | MLflow |
| `platform.dagster.availability` | Dagster |
| `platform.openmetadata.availability` | OpenMetadata |
| `platform.superset.availability` | Superset |

## Command

```bash
make operational-evidence
```

Optional:

```bash
make operational-evidence ALLOW_SLO_FAILURE=1
```

Emits JSON with SHA-256-bound `OperationalEvidenceManifest` plus in-repo
incident runbook bindings for demo failure, service health, lineage gaps, and
catalog portability.

## Limitations

- Measures **availability** only (pass/fail health checks), not latency budgets.
- Does not page/on-call — runbook bindings are references, not integrations.
- Full SLO alerting belongs to v3 operationalization (ADR-010/ADR-015).
