# v3 Planning (Production Infrastructure)

## Version

- Target version: v3.0.0
- Planning window: 2026 H2
- Owner: SoloLakehouse maintainers
- Status: draft

## 1. Goal and constraints

### Goal

- Upgrade v2 from internal MVP platform posture to production-capable platform posture.
- Introduce multi-environment reproducibility, stronger governance, and production operations standards.

### Non-goals

- No attempt to match full Databricks feature breadth in v3.
- No complete self-serve UX overhaul (reserved for v4 maturity focus).

### Constraints

- Time: staged rollout with reversible milestones
- Team capacity: small team, favor maintainable patterns over maximal complexity
- Compatibility requirements: preserve v2 execution semantics while infrastructure changes underneath

## 2. Current-state pain points

- Single-node Compose is not enough for production HA and environment parity.
- Security model is local-dev oriented (env var centric, limited RBAC/audit depth).
- Observability is still basic (structured logs but limited metrics/alert pipelines).
- Release promotion and rollback process are not yet environment-tiered.

Evidence:

- v2 timeline marks MVP suitability but not enterprise production readiness.
- Carry-forward risks in v2 history reference multi-env, security, and alerting gaps.

## 3. Architecture options

### Option A: Kubernetes + Helm + Terraform (selected direction)

- Summary: standardize runtime on K8s, package services with Helm, manage infra with Terraform.
- Pros: environment parity, scalability, ecosystem tooling, policy controls.
- Cons: higher operational complexity and learning burden.
- Risk level: medium.

### Option B: Keep Compose and harden host-level automation

- Summary: retain Compose and add scripts/ansible-like deployment hardening.
- Pros: lower short-term complexity.
- Cons: limited scalability/HA, weaker production posture.
- Risk level: medium-high (long-term).

### Option C: Managed cloud data platform migration

- Summary: move orchestration/storage/query stack to managed provider services.
- Pros: reduced infra ownership.
- Cons: major architectural shift and reduced educational/reference transparency.
- Risk level: high.

## 4. Decision

- Selected option: Option A (Kubernetes + Helm + Terraform), phased implementation.
- Why now: v2 solved orchestration semantics; bottleneck moved to production infrastructure and governance.
- Why not the others: Compose hardening under-delivers on HA/parity; managed migration changes project character too early.
- ADR link (if created): planned (`ADR-007-v3-production-infrastructure.md`).

## 5. Delivery plan

### Milestones

- M1: Base infra and deployment parity
  - Kubernetes baseline manifests/Helm chart skeletons
  - Terraform baseline for required resources
  - dev/staging environment split
- M2: Security and governance hardening
  - Secret management flow
  - access control baseline
  - auditability improvements
- M3: Reliability and operations model
  - metrics + alerting + dashboard baseline
  - release promotion gates and rollback runbooks
  - incident response checklists

### Verification gates

- Gate 1: Deploy same version to dev/staging from reproducible IaC pipeline.
- Gate 2: Recovery test passes for at least one critical service failure scenario.
- Gate 3: Production readiness checklist (security + observability + release controls) passes.

## 6. Release readiness criteria

- [ ] Deployment path is reproducible on a clean machine.
- [ ] Validation commands are documented and pass.
- [ ] Rollback path is tested.
- [ ] Upgrade notes from previous major version are documented.
- [ ] Multi-environment promotion flow is tested end-to-end.
- [ ] Baseline alerting coverage exists for critical pipeline failures.

## 7. Carry-forward notes

- Technical debt accepted in this version: temporary coexistence of Compose and K8s paths during migration.
- Items deferred to next version: deep self-serve UX maturity and wider productization tooling.
- Revisit triggers: operational burden too high for team size, or production incidents reveal governance blind spots.
