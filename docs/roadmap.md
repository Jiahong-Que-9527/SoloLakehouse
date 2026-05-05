# Roadmap

SoloLakehouse is now standardized on a **single v2.5 runtime path**.
Previous parallel runtime paths are retired from code and kept only as historical context in `docs/history/`.

## Version Status

| Version | Status | Theme |
|---------|--------|-------|
| v1.0 | Delivered (historical) | Runnable baseline lakehouse core |
| v2.0 | Delivered (historical) | Dagster orchestration introduction |
| v2.5 | Current baseline | Single-track orchestrated runtime + Iceberg Gold + OpenMetadata + Superset |
| v2.6 | Planned | Governance evidence bedrock (data contracts, lineage evidence pack, WORM audit) |
| v2.7 | Planned | Sovereignty & openness evidence (multi-engine Iceberg demo, sovereignty report, exit playbook) |
| v2.8 | Planned | ML compliance bedrock (MLflow ↔ Iceberg snapshot binding, auto model card aligned with EU AI Act) |
| v2.9 | Planned | Operational readiness (SLO emit, secrets discipline, promotion/rollback form, K8s readiness check) |
| v3.0 | Planned | Production runtime: Kubernetes + Helm + Terraform + multi-environment + managed secrets + alerting |
| v3.1 | Planned | AI compliance subsystems (decision evidence id, ComplianceRAG, AuditCopilot, LineageNarrator) |
| v4.0 | Planned | Self-serve usability and operational clarity |

> The v2.6 → v2.9 minor versions deliver the **governance, openness, ML compliance, and operational evidence** required by DORA / BaFin / EU AI Act on the existing Compose stack, so that v3.0 can focus purely on the runtime migration to Kubernetes. See `docs/history/v2.6-planning.md` through `v2.9-planning.md`.

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
