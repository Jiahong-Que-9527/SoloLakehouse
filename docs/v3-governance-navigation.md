# v3 Governance Navigation Map

## Why this page exists

This page is the single entrypoint for v3 governance planning, decision rationale, execution tasks, and operational runbooks.

Use it when you need to answer:

- What governance scope is in v3?
- Why were these governance choices made?
- How do we execute and validate governance rollout?
- Where is the operational evidence?

---

## 1) Governance storyline (v2 -> v3)

v2 establishes orchestration and internal MVP operations.  
v3 focuses on governance and productionization:

1. Environment governance (promotion and rollback discipline)
2. Access and secrets governance (least privilege, rotation, auditability)
3. Data governance (ownership, SLA, quality contracts)
4. Reliability governance (SLOs, alerting, incident handling)
5. Release governance (gates, readiness criteria, evidence)

---

## 2) Governance document map

### A. Strategy and planning

- `docs/roadmap.md`  
  Version-level direction and productionization framing.

- `docs/history/v3-planning.md`  
  v3 goals, options, milestones, gates, and carry-forward notes.

- `docs/governance-v3-matrix.md`  
  Governance domains, target state, acceptance criteria, and ownership model.

### B. Architecture decisions (ADRs)

- `docs/decisions/ADR-007-v3-k8s-helm-terraform.md`
- `docs/decisions/ADR-008-v3-environment-promotion.md`
- `docs/decisions/ADR-009-v3-secrets-and-access-governance.md`
- `docs/decisions/ADR-010-v3-observability-and-slo.md`
- `docs/decisions/ADR-011-v3-ml-productization-boundary.md`
- `docs/decisions/ADR-012-v3-data-governance-catalog-strategy.md`

### C. Execution backlog

- `docs/EVOLVING_PLAN.md` (Phase 4, Task 59+)

### D. Operations and release

- `docs/governance-v3-runbook.md`
- `docs/V3_RELEASE_CHECKLIST.md`
- `docs/release.md`

---

## 3) Execution flow (recommended)

```text
ADR alignment
   -> governance matrix baselining
      -> Phase 4 task execution
         -> runbook operationalization
            -> release checklist validation
               -> version history update
```

---

## 4) Governance readiness checkpoints

Before claiming v3 governance readiness, confirm all:

1. ADR decisions are reflected in implementation tasks.
2. Every governance matrix domain has evidence links.
3. Runbook workflows have been exercised (not just written).
4. Release checklist has no unresolved critical items.
5. Timeline and architecture-evolution history are updated.

---

## 5) Demo / architecture review usage

For architecture reviews and walkthroughs, use this page as your anchor:

1. Start with governance storyline (Section 1).
2. Show decision rigor via ADR set (Section 2B).
3. Show execution realism via task backlog (Section 2C).
4. Show operational maturity via runbook/checklist (Section 2D).

This helps demonstrate that governance is not aspirational only; it is documented as a complete decision-to-execution pipeline.
