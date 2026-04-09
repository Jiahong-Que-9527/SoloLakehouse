# v3 Planning (Production-Capable Platform Hardening)

## Version

- Target version: v3.0.0
- Planning window: 2026 H2
- Owner: SoloLakehouse maintainers
- Status: draft

## 1. Goal and constraints

### Goal

- Upgrade v2 from internal MVP platform posture to production-capable platform posture.
- Introduce multi-environment reproducibility, stronger governance, and production operations standards.
- Keep the project focused on platform productionization rather than feature expansion.

### Non-goals

- No attempt to match full Databricks feature breadth in v3.
- No complete self-serve UX overhaul (reserved for v4 maturity focus).
- No full online serving platform as a required v3 deliverable.
- No forced migration to a heavier metadata/catalog stack in v3.
- No expansion into Kafka, Flink, or other complex distributed systems without explicit scope change.

### Constraints

- Time: staged rollout with reversible milestones
- Team capacity: small team, favor maintainable patterns over maximal complexity
- Compatibility requirements: preserve v2 execution semantics while infrastructure changes underneath

### Priority order

1. Data governance baseline
2. Promotion and rollback controls
3. Reliability and observability
4. Security and access governance
5. ML experiment governance
6. Infrastructure (Kubernetes + Helm + Terraform)
7. CI/CD deployment pipeline

## 2. Current-state pain points

- Single-node Compose is not enough for production HA and environment parity.
- Security model is local-dev oriented (env var centric, limited RBAC/audit depth).
- Observability is still basic (structured logs but limited metrics/alert pipelines).
- Release promotion and rollback process are not yet environment-tiered.
- Governance metadata for key datasets is still limited and only partially standardized.
- ML tracking exists, but experiment governance and artifact lineage are not yet formalized enough for production-minded operation.

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

Additional scope decisions for v3:

- Keep `dev -> staging -> production` as the required promotion chain.
- Treat secrets, least-privilege access, and auditability as service-governance priorities.
- Use SLO-driven observability as the operations baseline.
- Keep a Hive-first governance baseline and defer heavier catalog replacement.
- Keep ML scope centered on experiment platform productionization, not full serving productization.

## 5. Delivery plan

### Workstreams and milestones

#### M1: Data governance baseline

- governance contracts for Gold and critical Silver outputs
- ownership, SLA, and quality metadata conventions
- naming conventions across environments

#### M2: Promotion and release controls

- formal `dev -> staging -> production` promotion flow
- promotion verification checklist
- rollback checklist and evidence model
- staged release rehearsal

#### M3: Reliability and observability

- minimal SLO set for critical services and pipelines
- metrics for orchestration success, freshness, latency, and quality pass rate
- alerting and dashboard baseline (Prometheus + Grafana)
- incident runbooks and drills

#### M4: Security and access governance

- managed secret flow and runtime injection pattern
- service-level credential boundary definition
- least-privilege access baseline
- auditability requirements for access changes

#### M5: ML experiment governance

- reproducible training and evaluation contracts
- stronger experiment metadata and artifact lineage
- future serving integration points documented, but serving deferred

#### M6: Infrastructure baseline

- Kubernetes baseline manifests / Helm chart skeletons
- Terraform baseline for required resources
- `dev` and `staging` environment split
- documented coexistence of local Compose path and v3 infra path

#### M7: CI/CD deployment pipeline

- GitOps approach decision (GitHub Actions Helm deploy vs. ArgoCD/FluxCD)
- automated Helm deployment to `dev` on merge to main
- post-deploy verification step
- manual promotion gates for `staging` and `production`

### Verification gates

- Gate 1: Deploy same version to dev/staging from reproducible IaC pipeline.
- Gate 2: Promotion from `dev` to `staging` succeeds with documented checks and rollback readiness.
- Gate 3: Recovery test passes for at least one critical service failure scenario.
- Gate 4: Production readiness checklist (security + observability + release controls) passes.

## 6. Release readiness criteria

- [ ] Deployment path is reproducible on a clean machine.
- [ ] Validation commands are documented and pass.
- [ ] Rollback path is tested.
- [ ] Upgrade notes from previous major version are documented.
- [ ] Multi-environment promotion flow is tested end-to-end.
- [ ] Baseline alerting coverage exists for critical pipeline failures.
- [ ] Critical datasets have governance contracts (`data_owner`, `refresh_sla`, `quality_class`).
- [ ] Secrets source and rotation / fallback process are documented.
- [ ] ML experiment workflow produces auditable metadata and artifact lineage.

## 7. Carry-forward notes

- Technical debt accepted in this version: temporary coexistence of Compose and K8s paths during migration.
- Items deferred to next version: deep self-serve UX maturity, complete serving productization, and heavier catalog/platform replacements if later justified.
- Revisit triggers: operational burden too high for team size, or production incidents reveal governance blind spots.

## 8. Scope guardrails

The following items are explicitly not required for v3 unless project scope changes:

- full online inference serving platform
- Superset / FastAPI as primary v3 delivery goals
- Keycloak-class end-user identity platform
- mandatory OpenMetadata / DataHub adoption
- complex streaming-first architecture

These may be considered later if they become scenario-driven rather than template-driven.
