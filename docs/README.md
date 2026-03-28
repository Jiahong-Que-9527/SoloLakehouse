# SoloLakehouse documentation

This directory documents SoloLakehouse as it evolves:

- **v1**: runnable and verifiable end-to-end lakehouse baseline
- **v2**: Dagster-orchestrated internal MVP platform
- **v3**: production-capable platform hardening

If you are starting with project positioning and version intent, read these first:

| Document | Description |
|----------|-------------|
| [roadmap.md](roadmap.md) | Canonical version roadmap and current v2 / planned v3 positioning |
| [SoloLakehouse v3 Spec](SoloLakehouse%20v3%20Spec) | Consolidated v3 scope, priorities, workstreams, and implementation direction |
| [history/v3-planning.md](history/v3-planning.md) | Formal v3 planning record: goals, constraints, milestones, release criteria |

Core docs:

| Document | Description |
|----------|-------------|
| [USER_GUIDE_EN.md](USER_GUIDE_EN.md) | **Complete user guide (English)** — installation, v1/v2 walkthrough, all UIs, v3 preview, troubleshooting |
| [USER_GUIDE.md](USER_GUIDE.md) | **完整用户指导书（中文）** — installation, v1/v2 walkthrough, all UIs, v3 preview, troubleshooting |
| [quickstart.md](quickstart.md) | Clone → `make up` → verify → pipeline → explore UIs, plus optional `make up-openmetadata` / `make up-superset` |
| [deployment.md](deployment.md) | Hardware/software prerequisites, full deployment, ports, troubleshooting |
| [architecture.md](architecture.md) | Layers, components, dependencies; includes optional OpenMetadata and Superset add-ons |
| [medallion-model.md](medallion-model.md) | Bronze / Silver / Gold paths, principles, Trino examples |
| [v1-to-v2-transition.md](v1-to-v2-transition.md) | Full narrative of v1 baseline, v1->v2 migration, and current v2 state |
| [DAGSTER_GUIDE.md](DAGSTER_GUIDE.md) | Dagster UI, jobs, schedules, reruns, and operational usage |
| [governance-v3-matrix.md](governance-v3-matrix.md) | Governance capability matrix and acceptance criteria for v3 productionization |
| [v3-governance-navigation.md](v3-governance-navigation.md) | Single-entry navigation map for v3 governance strategy, ADRs, tasks, runbook, and release readiness |
| [governance-v3-runbook.md](governance-v3-runbook.md) | Operational governance workflows (access, secrets, SLO breaches, incident communication) |
| [EVOLVING_PLAN.md](EVOLVING_PLAN.md) | Detailed, ordered implementation tasks (agents / developers) |
| [history/](history/README.md) | Version timeline, architecture evolution, and planning templates |
| [release.md](release.md) | Release runbook: validation, runtime checks, tagging |
| [V3_RELEASE_CHECKLIST.md](V3_RELEASE_CHECKLIST.md) | Productionization readiness checklist for v3.0 |
| [release-readiness.md](release-readiness.md) | Demo consistency check and pre-release self-check |
| [contributing.md](contributing.md) | How to contribute |
| [decisions/](decisions/README.md) | Architecture Decision Records (ADR-001 … ADR-014; see index for v1 / v2 / v2.5 / v3) |

**Diagrams:** Committed SVGs live under [`img/`](img/README.md); root `README.md` and `architecture.md` reference them.
