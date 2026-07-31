# Onboarding Reading Order

This guide gives someone **new to SoloLakehouse** a minimum path to a working mental model, then points to depth on demand. The stages are meant to be read in order; everything after stage 3 is reference material you consult when you need it.

**Quick anchors**

- **Runtime baseline**: v2.5 (single-track Docker Compose + Dagster + Trino + Iceberg + OpenMetadata + Superset). This runtime does not change before v3.0.
- **Current version**: v2.6 — the governance and evidence plane (data contracts + three-source lineage + audit manifest). Next up is v2.6.1.
- **Authoritative planning**: [`docs/roadmap.md`](roadmap.md) for what each version does, [`TASKS.md`](../TASKS.md) for what the next PR does.
- **Documentation index**: [`docs/README.md`](README.md).
- **Repository cheat-sheet for AI agents** (humans can skim it for commands and layout): [`CLAUDE.md`](../CLAUDE.md).

---

## Stage 0: get your bearings in 10 minutes (required)

Read in order to learn what this is, what it runs, and where its boundaries are.

| Order | Document | Purpose |
|------|------|------|
| 1 | [README.md](../README.md) | Project positioning, one-line architecture, quick-start entry point. |
| 2 | [docs/README.md](README.md) | Full documentation map — return here whenever you get lost. |
| 3 | [docs/roadmap.md](roadmap.md) | **Authoritative**: version status, measured delivery velocity, open decisions (D1–D3), and roadmap. |
| 4 | [docs/ASSESSMENT_LAKEHOUSE_DAX_ECB.md](ASSESSMENT_LAKEHOUSE_DAX_ECB.md) | Self-assessment: the honest boundaries of this reference implementation. |

---

## Stage 1: get it running and verify it (hands-on first)

Do this immediately after stage 0 — it is far more effective than continuing to read.

| Order | Document | Purpose |
|------|------|------|
| 5 | [docs/quickstart.md](quickstart.md) | Shortest path: clone → setup → verify → demo. |
| 6 | [docs/DEMO_RUNBOOK_EN.md](DEMO_RUNBOOK_EN.md) | Full demo and acceptance checklist. `make demo` is the acceptance entry point; `make pipeline` is the full pipeline including MLflow. |
| 7 | [docs/deployment.md](deployment.md) | Prerequisites, deployment, operations, and troubleshooting — come back here when something will not start. |

---

## Stage 2: using the platform day to day (operator / data consumer)

| Order | Document | Purpose |
|------|------|------|
| 8 | [docs/DAGSTER_GUIDE.md](DAGSTER_GUIDE.md) | Dagster jobs, schedules, UI, and runtime habits. |
| 9 | [docs/USER_GUIDE_EN.md](USER_GUIDE_EN.md) | Complete user-facing guide. |

---

## Stage 3: architecture and data contracts (required before changing code)

| Order | Document | Purpose |
|------|------|------|
| 10 | [docs/architecture.md](architecture.md) | Layers and component relationships. |
| 11 | [docs/medallion-model.md](medallion-model.md) | Bronze / Silver / Gold conventions and data contracts. |
| 12 | [docs/dataset-governance-naming.md](dataset-governance-naming.md) | Stable dataset IDs, physical mapping, and lineage-evidence naming rules. |
| 13 | [docs/v2.6-demo-goal.md](v2.6-demo-goal.md) | What the v2.6 governance-evidence capability is meant to prove, and its boundaries. |
| 14 | [docs/v2.6-release-readiness.md](v2.6-release-readiness.md) | The v2.6 evidence gate, the recorded drill, and the honest limitations. |
| 15 | [docs/object-store-abstraction.md](object-store-abstraction.md) | The S3-compatible object-store configuration boundary and why MinIO is retained. |
| 16 | [docs/decisions/README.md](decisions/README.md) | ADR index — skim the list, then open individual records as needed. |

**Suggested ADR priority (after the index)**

- **Why the stack looks like this**: ADR-001–005 (v1 trade-offs), ADR-006 (Dagster), ADR-020 (all-layer Iceberg — supersedes ADR-003 and ADR-013).
- **Directions under discussion**: ADR-016 (compute engine migration), ADR-007–012 (v3 infrastructure and governance), ADR-015 / ADR-017 / ADR-018.
- **v2.5 freeze trade-offs**: ADR-019 (SeaweedFS deferral).

You do not need to read every ADR on day one. Open the relevant number when you hit a specific decision point.

---

## Stage 4: version history, planning, and "what comes next"

Read when you need to answer "why is it shaped this way" or "what is the next version".

| Order | Document | Purpose |
|------|------|------|
| 17 | [TASKS.md](../TASKS.md) | **Authoritative** active backlog. Start here for what to build next. |
| 18 | [docs/history/README.md](history/README.md) | History navigation. |
| 19 | [docs/history/timeline.md](history/timeline.md) | Version-by-version timeline with decision gates. |
| 20 | [docs/history/architecture-evolution.md](history/architecture-evolution.md) | How the architecture evolved and which alternatives were rejected. |
| 21 | [docs/history/v3-planning.md](history/v3-planning.md) | v3 productionization and governance planning draft. |
| 22 | [task.md](../task.md) | Entity split, side-by-side upgrade, cutover, and rollback strategy. **Deferred indefinitely** (roadmap decision D2) — read only if you need that design reference. |

> **Note on superseded planning notes.** The version planning notes for v2.6–v2.9 were all written on 2026-05-05, before v2.6 implementation began, and conflict with the current roadmap in specific ways. They are maintained locally and are not published. Where you need planning intent, use [`docs/roadmap.md`](roadmap.md).

---

## Stage 5: v3 governance and release discipline (when preparing for production or governance work)

| Order | Document | Purpose |
|------|------|------|
| 23 | [docs/v3-governance-navigation.md](v3-governance-navigation.md) | Navigation for v3 governance topics. |
| 24 | [docs/governance-v3-matrix.md](governance-v3-matrix.md) | Governance matrix overview. |
| 25 | [docs/governance-v3-runbook.md](governance-v3-runbook.md) | Governance operations runbook. |
| 26 | [docs/v3-spec.md](v3-spec.md) | v3 specification and requirements (cross-check against the planning notes and ADRs). |
| 27 | [docs/compliance/README.md](compliance/README.md) | DORA, BaFin BAIT, and MiFID II evidence mappings. |

Also revisit the v3-related ADRs from stage 3 (007–012, 015).

---

## Stage 6: collaboration, release, and quality (when contributing or releasing)

| Order | Document | Purpose |
|------|------|------|
| 28 | [docs/contributing.md](contributing.md) | Contribution conventions. |
| 29 | [docs/git-workflow.md](git-workflow.md) | Branching and collaboration flow. |
| 30 | [docs/v2.5-acceptance-criteria.md](v2.5-acceptance-criteria.md) | v2.5 frozen-baseline Definition of Done — a useful bar to reference. |
| 31 | [CHANGELOG.md](../CHANGELOG.md) | Version history in Keep a Changelog format. |

> Some release runbooks and checklists are maintained locally and are not published. See "Local-only documents" in [docs/README.md](README.md).

---

## Only needed when working with AI agents or writing automation

- [docs/agent-prompts.md](agent-prompts.md) — prompts and workflow fragments for agent collaboration.

---

## A suggested first-week rhythm

| Day | Goal |
|------|------|
| Day 1 | Stages 0–1: get your bearings, run it locally, walk the demo runbook once. |
| Days 2–3 | Stages 2–3: user guide, architecture and medallion model, ADR index plus the core records. |
| Day 4 onward | Go deep by role: developers start from `TASKS.md`; platform and governance work goes to stage 5; releasing goes to stage 6. |

After stages 0–3 you can run the platform, troubleshoot it, and explain its architecture. Treat everything else as a dictionary to consult on demand.

---

## Documentation language policy

The public repository is **English-only**. Chinese-language working documents are maintained locally and excluded from publication via `.gitignore`. When adding documentation, write it in English.
