# Roadmap

SoloLakehouse is now standardized on a **single v2.5 runtime path**.
Previous parallel runtime paths are retired from code and kept only as historical context in `docs/history/`.

## Version Status

| Version | Status | Theme |
|---------|--------|-------|
| v1.0 | Delivered (historical) | Runnable baseline lakehouse core |
| v2.0 | Delivered (historical) | Dagster orchestration introduction |
| v2.5 | Current baseline | Single-track orchestrated runtime + Iceberg Gold + OpenMetadata + Superset |
| v3.0 | Planned | Production infrastructure and governance hardening |
| v4.0 | Planned | Self-serve usability and operational clarity |

## Current Baseline (v2.5)

The v2.5 baseline includes:
- Dagster as the only orchestration entrypoint (`make pipeline`)
- Trino with Hive and Iceberg catalogs
- Gold registration/refresh via Trino
- OpenMetadata in the default platform stack
- Superset in the default platform stack

Operational contract:
- `make up` starts the full mandatory stack
- `make verify` validates all core services and UIs
- `make pipeline` executes `full_pipeline_job`

## v3.0 Direction

Planned focus areas:
1. Multi-environment deployment model (Kubernetes/Helm/Terraform)
2. Promotion and rollback controls
3. Secrets and access governance
4. SLO-driven observability and incident operations
5. Governance baselines for critical datasets and ML lifecycle

## History References

For migration and legacy design context:
- [history/timeline.md](history/timeline.md)
- [history/architecture-evolution.md](history/architecture-evolution.md)
- [history/legacy-overview.md](history/legacy-overview.md)
