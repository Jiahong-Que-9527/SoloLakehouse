# SoloLakehouse Timeline

This file records project evolution in release order.

## v1.0.0 (2026-03-26) - Delivered

**Theme**
- Full v1 platform baseline with reliable deployment and validation workflow.

**What landed**
- Five-service core runs end-to-end: MinIO, PostgreSQL, Hive Metastore, Trino, MLflow.
- Hardened ingestion and transform pipeline with retries, quality checks, and rejected-record handling.
- CI quality gates for lint, typecheck, tests, and coverage baseline.
- Release workflow formalized (`docs/release.md`) with repeatable local verification.

**Architecture posture**
- Single-node Docker Compose reference architecture.
- Medallion data flow (Bronze/Silver/Gold) and ML experiment tracking in place.

**Carry-forward risks**
- No orchestrator yet (still script-based orchestration).
- Observability/UI layers from eight-layer target are not yet fully implemented.

**Decision gate to v2**
- Adopt orchestration (Dagster) without regressing simplicity of local setup.

---

## v2.0.0 (2026-03-26) - Current

**Theme**
- Orchestrated platform with Dagster assets, schedules, and operational UX.

**What landed**
- Dagster project scaffold with six software-defined assets: `ecb_bronze`, `dax_bronze`, `ecb_silver`, `dax_silver`, `gold_features`, `ml_experiment`.
- `full_pipeline_job` and weekday schedule (`daily_pipeline_schedule`, 06:00 UTC) wired through `Definitions`.
- Compose integration adds `dagster-webserver` and `dagster-daemon` with persistent Dagster storage configuration.
- Default execution path switched to Dagster (`make pipeline`), with `make pipeline-legacy` retained as migration fallback.
- Operational docs added (`docs/DAGSTER_GUIDE.md`) and architecture docs updated with orchestration layer and dependency graph.
- Data freshness sensor (`ecb_data_freshness_sensor`) and gold data quality gate (`gold_features` asset check, min rows) added.

**Primary decision gate**
- Keep script fallback vs full orchestrator-only mode.

**Carry-forward risks**
- Dual execution paths increase operational surface during transition period.
- Legacy script removal decision still pending; keeping both paths has maintenance overhead.
- Full production hardening (multi-environment infra, secret lifecycle, alerting) is deferred to later versions.

**Decision gate to v3**
- Decide whether to remove legacy script path and standardize on orchestrator-only execution before infrastructure migration.

---

## v3.0.0 - Planned

**Theme**
- Production infrastructure (Kubernetes/Helm/Terraform).

**Expected outcomes**
- Environment reproducibility beyond single host.
- Deployment model that supports team-scale operations.

**Primary decision gate**
- Portability-first minimal stack vs cloud-specific optimizations.

---

## v4.0.0 - Planned

**Theme**
- Self-serve maturity and operational clarity.

**Expected outcomes**
- Better onboarding, diagnostics, and failure guidance for end users.

**Primary decision gate**
- Feature breadth vs maintenance burden.
