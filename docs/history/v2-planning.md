# v2 Planning (Orchestrated Platform)

## Version

- Target version: v2.0.0
- Planning window: 2026 Q2
- Owner: SoloLakehouse maintainers
- Status: delivered

## 1. Goal and constraints

### Goal

- Introduce Dagster orchestration for the full data/ML asset chain.
- Preserve local developer ergonomics and rollback capability.

### Non-goals

- No Kubernetes migration in v2.
- No full observability platform rollout (Prometheus/Grafana) in v2 core.

### Constraints

- Time: deliver iteratively with small, verifiable steps.
- Team capacity: optimize for solo/small-team maintenance.
- Compatibility requirements: keep legacy script path available during migration.

## 2. Current-state pain points

- Linear script orchestration has limited scheduling and lineage visibility.
- Retry behavior is step-based, not asset-native.
- Re-run granularity is coarse.

Evidence:

- v1 uses `scripts/run-pipeline.py` for all orchestration.
- Roadmap and EVOLVING_PLAN explicitly target Dagster in v2.

## 3. Architecture options

### Option A: Dagster (selected direction)

- Summary: software-defined assets + job + schedule + UI.
- Pros: lineage, scheduling, retries, operational UX.
- Cons: additional runtime complexity and dependencies.
- Risk level: medium.

### Option B: Keep script + cron

- Summary: continue script orchestration, add scheduler wrappers.
- Pros: lowest complexity increase.
- Cons: weak lineage and asset-level ergonomics.
- Risk level: medium (long-term maintainability risk).

### Option C: Alternative orchestrator (Airflow/Prefect)

- Summary: replace with another orchestrator stack.
- Pros: ecosystem familiarity (team dependent).
- Cons: migration overhead and reduced alignment with current plan.
- Risk level: high (scope shift).

## 4. Decision

- Selected option: Option A (Dagster).
- Why now: v1 baseline is stable; orchestration is next highest-leverage gap.
- Why not the others: script+cron insufficient long-term; switching orchestrator family now increases scope risk.
- ADR link: architecture rationale captured in `docs/history/architecture-evolution.md` (v2 section).

## 5. Delivery plan

### Milestones

- M1: Task 37-39 (deps + scaffold + resources)
- M2: Task 40-45 (assets + job + schedule + definitions)
- M3: Task 46-50 (Docker/Compose/Makefile integration + legacy compatibility)

### Verification gates

- [x] Gate 1: `dagster asset list -f dagster/definitions.py` shows 6 assets.
- [x] Gate 2: Dagster services start via compose and UI is reachable.
- [x] Gate 3: legacy and Dagster execution paths are both operable.

## 6. Release readiness criteria

- [x] Deployment path is reproducible on a clean machine.
- [x] Validation commands are documented and pass.
- [x] Rollback path is tested.
- [x] Upgrade notes from previous major version are documented.

## 7. Carry-forward notes

- Technical debt accepted in this version: temporary dual orchestration path.
- Items deferred to next version: optional custom Dagster IO manager and broader observability rollout.
- Revisit triggers: stable Dagster adoption across repeated runs; no critical regressions in local setup.
