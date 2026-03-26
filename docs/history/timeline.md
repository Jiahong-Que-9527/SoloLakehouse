# SoloLakehouse Timeline

This file records project evolution in release order.

## v1.0.0 (2026-03-26) - Current

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

## v2.0.0 - Planned

**Theme**
- Orchestrated platform with Dagster assets, schedules, and operational UX.

**Expected outcomes**
- Replace linear orchestration path for default runs.
- Add scheduling/retry semantics per asset.
- Improve rerun ergonomics and lineage visibility.

**Primary decision gate**
- Keep script fallback vs full orchestrator-only mode.

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
