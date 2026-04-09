# TASKS.md — SoloLakehouse Current Execution Backlog

> This file is the working task board for the **current repository state**.
> It replaces the old v1 build-out checklist with a backlog aligned to the shipped platform:
>
> - `v1.0` delivered: runnable lakehouse baseline
> - `v2.0` delivered/current path: Dagster orchestration
> - `v2.5` delivered/reference: Iceberg Gold + optional OpenMetadata + optional Superset
> - `v3.0` next: production-capable platform hardening
>
> Use this file for day-to-day execution ordering.
> Use `docs/roadmap.md` for version framing and `docs/EVOLVING_PLAN.md` for the detailed version history.

## Current Status

### Delivered baseline

- [x] Lakehouse core on Docker Compose: MinIO, PostgreSQL, Hive Metastore, Trino, MLflow
- [x] Bronze/Silver/Gold medallion flow with schema validation and rejected-record handling
- [x] Dagster asset orchestration, schedule, sensor, and asset check
- [x] Legacy pipeline fallback path retained
- [x] Gold Iceberg table in Trino
- [x] Optional OpenMetadata profile
- [x] Optional Superset profile
- [x] Unit and integration test foundations
- [x] Demo and release-readiness documentation

### Current bottleneck

- [ ] Production-capable environment model (`dev -> staging -> production`)
- [ ] Promotion and rollback discipline
- [ ] Secrets and access governance
- [ ] SLO-driven observability and alerting
- [ ] Governance contracts for key datasets
- [ ] ML experiment governance hardening
- [ ] Kubernetes / Helm / Terraform delivery path

## How To Use This File

- Execute blocks in order unless a task explicitly says otherwise.
- Mark completed items with `[x]`.
- Keep Docker Compose as the default local/demo path while v3 work is in progress.
- When a block is materially completed, update:
  - `docs/history/timeline.md`
  - `docs/history/architecture-evolution.md`
  - the relevant planning doc under `docs/history/`

## Primary References

- `README.md`
- `docs/roadmap.md`
- `docs/architecture.md`
- `docs/EVOLVING_PLAN.md`
- `docs/history/v3-planning.md`
- `docs/governance-v3-matrix.md`
- `docs/governance-v3-runbook.md`
- `docs/V3_RELEASE_CHECKLIST.md`
- `docs/decisions/ADR-007-v3-k8s-helm-terraform.md`
- `docs/decisions/ADR-008-v3-environment-promotion.md`
- `docs/decisions/ADR-009-v3-secrets-and-access-governance.md`
- `docs/decisions/ADR-010-v3-observability-and-slo.md`
- `docs/decisions/ADR-011-v3-ml-productization-boundary.md`
- `docs/decisions/ADR-012-v3-data-governance-catalog-strategy.md`

---

## Block A — Governance Contracts First

Goal: define the operating contract for the platform before changing runtime infrastructure.

### A1. Dataset governance baseline

- [ ] Create a lightweight governance registry for key datasets:
  - Gold: `ecb_dax_features`
  - Gold: `ecb_dax_features_iceberg`
  - Critical Silver: ECB cleaned and DAX cleaned outputs
- [ ] For each governed dataset, record:
  - `data_owner`
  - `business_purpose`
  - `refresh_sla`
  - `quality_class`
  - `consumers`
  - `source_of_truth`
- [ ] Decide where this contract lives in-repo and document the convention.
- [ ] Add documentation describing how governance metadata is updated during schema or semantics changes.

### A2. Quality gate tightening

- [ ] Review current Dagster asset checks and identify missing checks for critical Silver and Gold outputs.
- [ ] Add at least one freshness-oriented check and one schema/shape-oriented check for Gold outputs.
- [ ] Define threshold rationale in docs so checks are not "magic numbers".
- [ ] Ensure failed checks are visible in the main runbook and release path.

### A3. Ownership and naming

- [ ] Standardize dataset naming and environment naming conventions across `dev`, `staging`, and `production`.
- [ ] Document service ownership and on-call owner mapping for small-team operation.
- [ ] Link ownership expectations into governance docs and release checklist.

Exit criteria:

- [ ] Key Gold and critical Silver datasets have documented contracts.
- [ ] Governance metadata has a clear storage location and update workflow.
- [ ] Dataset quality expectations are reflected in both code and docs.

---

## Block B — Promotion, Release, and Rollback

Goal: make the platform operable across environments before introducing Kubernetes complexity.

### B1. Environment model

- [ ] Define the minimum supported environment chain: `dev -> staging -> production`.
- [ ] Document what "production-like" means for this repo before full production rollout.
- [ ] Split configuration into environment-aware inputs rather than one local-default shape.
- [ ] Define which services are required in every environment and which remain optional.

### B2. Promotion flow

- [ ] Turn the v3 promotion narrative into an executable checklist with clear entry and exit conditions.
- [ ] Define what evidence is required to promote from:
  - `dev` to `staging`
  - `staging` to `production`
- [ ] Identify the exact validation commands for each environment.
- [ ] Define failure-handling rules when promotion checks partially pass.

### B3. Rollback readiness

- [ ] Write a versioned rollback procedure for application releases.
- [ ] Write a separate rollback procedure for schema / metadata / catalog changes.
- [ ] Add a rollback owner role to the v3 release checklist.
- [ ] Rehearse at least one rollback scenario and capture evidence.

### B4. Release automation foundation

- [ ] Add a script or Make target that bundles the required pre-promotion validations.
- [ ] Ensure release validation covers the Dagster default path and any still-supported compatibility path.
- [ ] Define release artifact versioning rules for app code, Helm charts, and infra changes.

Exit criteria:

- [ ] Promotion flow is documented and runnable.
- [ ] Rollback steps are tested, not just written.
- [ ] Environment-specific release evidence can be attached to a release decision.

---

## Block C — Observability and Incident Readiness

Goal: move from logs and ad hoc checks to SLO-backed operations.

### C1. Minimal SLO set

- [ ] Define the initial SLOs for critical outcomes:
  - pipeline success rate
  - Gold freshness
  - asset-check pass rate
  - end-to-end pipeline latency
- [ ] Record target values, measurement windows, and breach actions.
- [ ] Keep the first SLO set intentionally small and maintainable.

### C2. Metrics and dashboards

- [ ] Map existing runtime signals to required SLO metrics.
- [ ] Implement missing metric emission for freshness, success/failure, and latency.
- [ ] Create a baseline dashboard plan for:
  - orchestration health
  - data freshness
  - quality-check pass rate
  - service health

### C3. Alerting and runbooks

- [ ] Define alert rules for critical pipeline failure and SLO breach conditions.
- [ ] Link every alert to an operator action in `docs/governance-v3-runbook.md`.
- [ ] Add at least 3 realistic incident drill scenarios.
- [ ] Run at least one drill and record what was missing.

Exit criteria:

- [ ] Minimal SLO set is documented.
- [ ] Critical alerts exist with clear owner/action mapping.
- [ ] Incident drill evidence exists for at least one realistic failure case.

---

## Block D — Secrets and Access Governance

Goal: remove local-dev security assumptions from the target runtime model.

### D1. Secrets model

- [ ] Document the target secrets flow for v3:
  - source of truth
  - injection mechanism
  - rotation flow
  - emergency fallback
- [ ] List all current secrets/env vars and classify them by risk and owner.
- [ ] Separate "safe local defaults" from "managed runtime secret" expectations.

### D2. Access model

- [ ] Define service identities and least-privilege expectations for:
  - Dagster
  - Trino
  - Hive Metastore
  - MLflow
  - object storage access
- [ ] Document which permissions are needed by service and by environment.
- [ ] Add an access-change evidence template aligned with the governance runbook.

### D3. Rotation and auditability

- [ ] Create a secrets rotation drill plan.
- [ ] Define what audit evidence must exist for access changes and secret rotations.
- [ ] Validate at least one secret rotation workflow in a non-production environment.

Exit criteria:

- [ ] Managed-secrets direction is explicit and documented.
- [ ] Critical services have a least-privilege access model.
- [ ] Rotation and access-change workflows have evidence requirements.

---

## Block E — ML Governance and Reproducibility

Goal: strengthen the ML experiment platform without expanding into full serving.

### E1. Reproducibility contracts

- [ ] Define the minimum metadata required for every training/evaluation run.
- [ ] Ensure training inputs, feature version, model version, and evaluation outputs are traceable.
- [ ] Document the approved ML boundary: experiment platform productionization first, serving deferred.

### E2. Artifact lineage

- [ ] Review current MLflow artifacts and identify missing lineage fields.
- [ ] Add explicit linkage from trained model runs back to Gold dataset version or run context.
- [ ] Make it possible to answer: "which data and code produced this model?"

### E3. Validation and release posture

- [ ] Define what constitutes a valid ML experiment run for release readiness.
- [ ] Add ML governance evidence to the v3 release checklist if needed.

Exit criteria:

- [ ] ML runs are auditable and reproducible enough for v3 target scope.
- [ ] Serving remains explicitly out of scope unless roadmap changes.

---

## Block F — Kubernetes and Helm Introduction

Goal: introduce Kubernetes only after the operating model above is clear.

### F1. Scope guardrails before cluster work

- [ ] Confirm Blocks A-D are materially underway before starting broad K8s migration.
- [ ] Keep Compose as the default local and demo path.
- [ ] Limit the first K8s milestone to environment reproducibility, not full platform sophistication.

### F2. Helm chart baseline

- [ ] Create an initial Helm chart structure for the core runtime.
- [ ] Decide which services are in scope for the first K8s path versus left local/optional.
- [ ] Establish values layering for `dev`, `staging`, and `production`.
- [ ] Add probes, config injection patterns, and resource requests/limits where applicable.

### F3. Runtime migration strategy

- [ ] Define the order of service migration to K8s.
- [ ] Decide whether some dependencies remain managed/external for the first v3 milestone.
- [ ] Document coexistence of Compose and K8s paths during transition.

### F4. CI/CD deployment pipeline

- [ ] Choose and document the GitOps approach for K8s deployments (GitHub Actions–driven Helm deploy vs. ArgoCD/FluxCD).
- [ ] Create a GitHub Actions workflow that deploys the Helm chart to the `dev` environment on merge to main.
- [ ] Add a post-deploy verification step (smoke test or service health check) to the deployment workflow.
- [ ] Define the manual promotion gate for `staging` and `production` (explicit approval step or triggered deployment).
- [ ] Ensure the local Compose path remains unaffected by CI/CD additions.

Exit criteria:

- [ ] Helm baseline exists for the first supported runtime slice.
- [ ] Environment-specific values strategy is defined.
- [ ] K8s migration scope is phased and documented.
- [ ] CI/CD pipeline is operational for the `dev` environment.
- [ ] Promotion gates for `staging` and `production` are defined.

---

## Block G — Terraform Introduction

Goal: use Terraform when environment resources need reproducible provisioning, not before.

### G1. Terraform adoption trigger

- [ ] Start Terraform only once the target environment topology is clear enough to codify.
- [ ] Document the boundary between:
  - Terraform-managed infrastructure
  - Helm-managed application deployment
  - repo-local Compose development flow

### G2. Baseline modules

- [ ] Define the minimum Terraform resource set required for `dev` and `staging`.
- [ ] Decide which resources belong in the first baseline:
  - Kubernetes cluster or cluster access dependencies
  - object storage
  - database
  - secrets integration
  - networking
- [ ] Keep the initial module set intentionally small and reviewable.

### G3. Promotion alignment

- [ ] Ensure Terraform state/layout supports the `dev -> staging -> production` promotion model.
- [ ] Define plan/apply review expectations and evidence capture.
- [ ] Document rollback expectations for infrastructure changes.

Exit criteria:

- [ ] Terraform has a clear scope boundary and environment model.
- [ ] Initial modules provision the minimum required target resources.
- [ ] Infra change review and rollback expectations are documented.

---

## Recommended Execution Order

1. Block A — Governance Contracts First
2. Block B — Promotion, Release, and Rollback
3. Block C — Observability and Incident Readiness
4. Block D — Secrets and Access Governance
5. Block E — ML Governance and Reproducibility
6. Block F — Kubernetes and Helm Introduction
7. Block G — Terraform Introduction

## Notes On Timing

- Kubernetes should begin when multi-environment deployment and release controls are defined, not while those rules are still implicit.
- Terraform should begin when the target environment topology is stable enough to codify as infrastructure, not while runtime ownership is still being debated.
- OpenMetadata and Superset remain optional extensions unless roadmap scope changes.
- v3 should continue to emphasize productionization over broad feature expansion.
