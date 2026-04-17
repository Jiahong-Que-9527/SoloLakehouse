# v3 Governance Capability Matrix

## Purpose

This matrix defines governance capabilities required to move SoloLakehouse from the v2.5 local/reference baseline to v3 production-capable suitability.

## How to use

- Treat each row as a governance workstream.
- Mark progress by environment (`dev`, `staging`, `production`).
- Link implementation PRs and runbook evidence before marking complete.

---

## Governance Matrix

| Domain | Current (v2.5 baseline) | Target (v3) | Acceptance Criteria | Primary Artifact |
|---|---|---|---|---|
| Environment governance | Single-node local-first with limited promotion semantics | Formal `dev -> staging -> production` promotion flow | Promotion checklist enforced; rollback criteria documented and tested | `docs/decisions/ADR-008-v3-environment-promotion.md` |
| Access governance | Env-var driven local credentials, coarse controls | Least-privilege service identities and audited access changes | Service credentials scoped by role; access change log retained | `docs/decisions/ADR-009-v3-secrets-and-access-governance.md` |
| Secrets governance | `.env`-centric defaults suitable for local use | Managed secrets lifecycle with rotation and emergency fallback policy | Secrets source documented; rotation runbook validated | `docs/decisions/ADR-009-v3-secrets-and-access-governance.md` |
| Data governance | Hive-first catalog with limited policy metadata | Hive-first governance baseline + ownership/SLA/quality metadata contracts | Dataset ownership map exists; SLA and quality class defined for key datasets | `docs/decisions/ADR-012-v3-data-governance-catalog-strategy.md` |
| Observability governance | Structured logs and basic runtime telemetry | SLO-driven metrics, alerting, and dashboard baseline | Critical alerts wired; SLO definitions and breach actions documented | `docs/decisions/ADR-010-v3-observability-and-slo.md` |
| Incident governance | Ad-hoc troubleshooting flow | Standardized incident runbooks and recovery drills | 3+ failure drills executed and documented | `docs/governance-v3-runbook.md`, `TASKS.md` |
| Release governance | Single-path release checks on the v2.5 baseline | Multi-environment gated release with rollback validation | Release gate evidence attached to every production promotion | `docs/release.md`, `docs/V3_RELEASE_CHECKLIST.md` |
| ML governance boundary | Experiment tracking present, serving scope undefined | Experiment platform productionization first; serving expansion explicitly gated | ML artifact lineage and evaluation contracts documented | `docs/decisions/ADR-011-v3-ml-productization-boundary.md` |

---

## Suggested owner model

- Platform owner: infra, promotion, release governance
- Data platform owner: catalog and data governance contracts
- Reliability owner: observability, SLO, incident drills
- ML platform owner: experiment governance and boundary controls

For small teams, one person can hold multiple roles, but each workstream still needs explicit ownership.

---

## Exit criteria for v3 governance readiness

v3 governance can be considered complete when:

1. Every matrix row has an implemented artifact and operational evidence.
2. Promotion + rollback has been exercised end-to-end in at least one staged release.
3. Incident response runbooks have been validated against realistic failure drills.
4. Governance controls remain usable by a small team (no excessive operational burden).
