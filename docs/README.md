# SoloLakehouse Documentation

This documentation set treats **v2.5 as the only active runtime baseline**.
Historical version narratives are preserved under `docs/history/`.

## Start Here

| Document | Purpose |
|----------|---------|
| [ONBOARDING_READING_ORDER.md](ONBOARDING_READING_ORDER.md) | Suggested reading order for new maintainers (新接手者文档阅读顺序) |
| [roadmap.md](roadmap.md) | Canonical version status and forward roadmap |
| [ASSESSMENT_LAKEHOUSE_DAX_ECB.md](ASSESSMENT_LAKEHOUSE_DAX_ECB.md) | Self-assessment: where this reference implementation is honest about its limits |
| [quickstart.md](quickstart.md) | Fast local run: clone -> up -> verify -> pipeline |
| [../DEMO.md](../DEMO.md) | Fixed 20-30 minute v2.5 recording script |
| [make-demo-guide.md](make-demo-guide.md) | Detailed `make demo` explanation and manual execution guide |
| [../RUNBOOK.md](../RUNBOOK.md) | Operational runbook for common local-stack scenarios |
| [DEMO_RUNBOOK.md](DEMO_RUNBOOK.md) | 完整 Demo 执行手册（中文，含验收清单与结论模板） |
| [DEMO_RUNBOOK_EN.md](DEMO_RUNBOOK_EN.md) | Full demo runbook in English (with acceptance checklist) |
| [deployment.md](deployment.md) | Prerequisites, deployment, operations, troubleshooting |
| [DAGSTER_GUIDE.md](DAGSTER_GUIDE.md) | Dagster operations and runtime usage |

## User Guides

| Document | Purpose |
|----------|---------|
| [USER_GUIDE_EN.md](USER_GUIDE_EN.md) | Full user guide in English |
| [USER_GUIDE.md](USER_GUIDE.md) | 完整用户指导书（中文） |

## Architecture and Data

| Document | Purpose |
|----------|---------|
| [architecture.md](architecture.md) | Layered architecture and component relationships |
| [entity-template-readiness.md](entity-template-readiness.md) | Phase 1 readiness evidence for using SoloLakehouse as the repeatable product-entity template |
| [product-entity-contract.md](product-entity-contract.md) | Required identity, storage, runtime, and metadata fields for FinLakehouse/Aviation product entities |
| [dataset-governance-naming.md](dataset-governance-naming.md) | Stable logical dataset IDs and physical mapping rules for entity governance |
| [object-store-abstraction.md](object-store-abstraction.md) | Object-store configuration boundary and MinIO deferral strategy for entity split |
| [runtime-state-layout.md](runtime-state-layout.md) | Entity-owned runtime roots, bind mount ownership, `.env`, and side-by-side state layout |
| [entity-backup-restore-runbook.md](entity-backup-restore-runbook.md) | Minimum backup set, restore order, and validation checks for a product entity |
| [restore-drills/2026-05-17-entity-template-restore-drill.md](restore-drills/2026-05-17-entity-template-restore-drill.md) | Completed v2.5 entity-template restore drill evidence for issue #10 |
| [medallion-model.md](medallion-model.md) | Bronze/Silver/Gold conventions and data contracts |
| [decisions/README.md](decisions/README.md) | ADR index (including v2.5 decisions) |
| [compliance/README.md](compliance/README.md) | DORA, BaFin BAIT, and MiFID II / MiFIR evidence mappings |

## Release and Quality

| Document | Purpose |
|----------|---------|
| [release.md](release.md) | Release runbook |
| [release-readiness.md](release-readiness.md) | Pre-release readiness checks |
| [V3_RELEASE_CHECKLIST.md](V3_RELEASE_CHECKLIST.md) | v3 planning checklist |

## Historical and Legacy Records

| Document | Purpose |
|----------|---------|
| [history/README.md](history/README.md) | History index |
| [history/timeline.md](history/timeline.md) | Version timeline |
| [history/architecture-evolution.md](history/architecture-evolution.md) | Architecture decision evolution |
| [history/legacy-overview.md](history/legacy-overview.md) | Legacy runtime/archive map |

Diagrams are under [img/](img/README.md).
