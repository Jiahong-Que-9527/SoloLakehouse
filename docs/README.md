# SoloLakehouse Documentation

**v2.5 is the protected runtime baseline** — the Docker Compose stack does not
change until v3.0. **v2.9 is delivered on `main`**; the active backlog is
**Block `L` / `L4` Phase 1** — live batch sources ECB (DFR/MLF) + EWG (Alpha
Vantage) through the full medallion path. Phase 2 (streaming/crypto) is
deferred until Phase 1 lands. Historical version narratives are preserved
under `docs/history/`.

Two documents are authoritative:

- **[roadmap.md](roadmap.md)** — what each version does
- **[../TASKS.md](../TASKS.md)** — what the next PR does

Where any other document disagrees with those two, those two win. The version
planning notes for v2.6–v2.9 are superseded 2026-05-05 snapshots kept locally
and not published; follow the two authoritative documents instead.

> Some documents referenced by maintainers are intentionally local-only and are
> not part of the public repository (release checklists, dated CN state
> snapshots, the generated documentation compendium). They are listed under
> "Local-only documents" at the end of this index rather than linked inline.

## Start Here

| Document | Purpose |
|----------|---------|
| [ONBOARDING_READING_ORDER.md](ONBOARDING_READING_ORDER.md) | Suggested reading order for new maintainers |
| [../TASKS.md](../TASKS.md) | Active execution backlog — canonical "what to build next" |
| [roadmap.md](roadmap.md) | Canonical version status, delivery velocity, and open decisions |
| [ASSESSMENT_LAKEHOUSE_DAX_ECB.md](ASSESSMENT_LAKEHOUSE_DAX_ECB.md) | Self-assessment: where this reference implementation is honest about its limits |
| [quickstart.md](quickstart.md) | Fast local run: clone -> up -> verify -> pipeline |
| [../DEMO.md](../DEMO.md) | Fixed 20-30 minute v2.5 recording script |
| [make-demo-guide.md](make-demo-guide.md) | Detailed `make demo` explanation and manual execution guide |
| [../RUNBOOK.md](../RUNBOOK.md) | Operational runbook for common local-stack scenarios |
| [DEMO_RUNBOOK_EN.md](DEMO_RUNBOOK_EN.md) | Full demo runbook in English (with acceptance checklist) |
| [deployment.md](deployment.md) | Prerequisites, deployment, operations, troubleshooting |
| [DAGSTER_GUIDE.md](DAGSTER_GUIDE.md) | Dagster operations and runtime usage |

## User Guides

| Document | Purpose |
|----------|---------|
| [USER_GUIDE_EN.md](USER_GUIDE_EN.md) | Full user guide in English |

## Architecture and Data

| Document | Purpose |
|----------|---------|
| [architecture.md](architecture.md) | Layered architecture and component relationships |
| [layer1-source-selection-criteria.md](layer1-source-selection-criteria.md) | Block `L` / `L1` — mandatory gates and scoring rubric for Layer 1 source research |
| [layer1-source-survey.md](layer1-source-survey.md) | Block `L` / `L2` — research-only candidate survey and `L3` decision checklist |
| [entity-template-readiness.md](entity-template-readiness.md) | Phase 1 readiness evidence for using SoloLakehouse as the repeatable product-entity template |
| [product-entity-contract.md](product-entity-contract.md) | Required identity, storage, runtime, and metadata fields for FinLakehouse/Aviation product entities |
| [finlakehouse-deployment-guide.md](finlakehouse-deployment-guide.md) | Optional VPS walkthrough for the first independent FinLakehouse entity |
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
| [v2.6-release-readiness.md](v2.6-release-readiness.md) | v2.6 lineage-evidence release gate, recorded drill, and honest limitations |
| [v2.5-acceptance-criteria.md](v2.5-acceptance-criteria.md) | v2.5 frozen-baseline Definition of Done |
| [../CHANGELOG.md](../CHANGELOG.md) | Version history in Keep a Changelog format |

## Historical and Legacy Records

| Document | Purpose |
|----------|---------|
| [history/README.md](history/README.md) | History index |
| [history/timeline.md](history/timeline.md) | Version timeline |
| [history/architecture-evolution.md](history/architecture-evolution.md) | Architecture decision evolution |
| [history/legacy-overview.md](history/legacy-overview.md) | Retired runtime paths and archive map |
| [history/planning-template.md](history/planning-template.md) | Reusable version-planning template |
| [history/v2-planning.md](history/v2-planning.md) | Delivered v2 planning |
| [history/v2.5-planning.md](history/v2.5-planning.md) | Delivered v2.5 planning |
| [history/v3-planning.md](history/v3-planning.md) | Planned v3 production runtime |

### Superseded planning notes (2026-05-05 snapshots)

All four were written on a single day, before v2.6 implementation began. They
carry a SUPERSEDED banner listing their known deviations. Read them for
historical context; follow [roadmap.md](roadmap.md) and [../TASKS.md](../TASKS.md)
for instructions.

| Document | Superseded because |
|----------|--------------------|
| `history/v2.6-planning.md` *(local-only)* | Delivered; two dropped items moved to v2.6.1 (`J1`, `J2`) |
| `history/v2.7-planning.md` *(local-only)* | Its primary gate (4-engine demo) is explicitly rejected by the current roadmap |
| `history/v2.8-planning.md` *(local-only)* | Its timing rationale (EU AI Act `2026-08-02`) has passed |
| `history/v2.9-planning.md` *(local-only)* | Assumes the superseded six-month milestone plan |
| [v2.6-execution-plan.md](v2.6-execution-plan.md) | v2.6 execution order — delivered |

## Project State Snapshots (dated, do not retroactively edit)

| Document | Purpose |
|----------|---------|
| [project-state-overview-2026-05-05.md](project-state-overview-2026-05-05.md) | EN snapshot — v2.5 baseline overview |

## Local-only documents (not in the public repository)

These exist in maintainer working copies and are intentionally excluded from the
published repository. They are listed here so their absence is not mistaken for
an oversight:

- `DOCUMENTATION_COMPENDIUM.md` — generated aggregate of all docs
- `release.md`, `release-readiness.md` — internal release runbooks
- `V1_RELEASE_CHECKLIST.md`, `V2_RELEASE_CHECKLIST.md`, `V3_RELEASE_CHECKLIST.md`
- Chinese-language working documents: dated state snapshots, the enterprise
  evolution note, and the v2.6–v2.9 version planning notes
- Chinese-language user guide and demo runbook (English equivalents are published)

Diagrams are under [img/](img/README.md).
