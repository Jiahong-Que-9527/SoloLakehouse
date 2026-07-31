# SoloLakehouse v3 Spec

> ## Status note — 2026-07-31
>
> This spec was written before the v2.6–v2.9 evidence series was defined. Two of
> its assumptions have since been overtaken:
>
> - **Workstream 5 (data governance baseline) is largely delivered.** v2.6 ships
>   machine-validated contracts in `governance/datasets/*.yaml` carrying `owner`,
>   `refresh_sla`, `quality_class`, `classification`, `retention`, and lineage
>   relationships, enforced by `make validate-contracts` in CI. v3 inherits this
>   rather than building it.
> - **The "do not force OpenMetadata adoption" constraint is obsolete.**
>   OpenMetadata has been a mandatory component of the default stack since v2.5,
>   and v2.6's lineage evidence depends on it.
>
> Everything else below still stands. Current authority for version scope is
> [`roadmap.md`](roadmap.md); v2.9 is the version that prepares the readiness
> gates this spec assumes.

## Goal

Move SoloLakehouse from:

> v2.5 — a local reference runtime: single-track Dagster orchestration + all-layer Iceberg + OpenMetadata + Superset

to:

> v3 — a platform reference implementation with production-capable deployment, governance, observability, and release control

---

## Core principle

v3 is not about extending data features; it is about completing platform capabilities.

Priorities, in order:

1. Reproducible multi-environment deployment
2. Governance and security baseline
3. Observability and reliability
4. Release, rollback, and operations process

In one line:

> Focus on platform productionization, not feature expansion.

---

## v3 scope boundary

### Should be prioritized

- a Kubernetes / Helm / Terraform multi-environment deployment baseline
- a `dev -> staging -> production` promotion and rollback mechanism
- secrets lifecycle, least privilege, and access auditability
- SLO-driven metrics, alerting, dashboards, and runbooks
- dataset governance conventions: owner, refresh SLA, quality class, lineage responsibility *(largely delivered in v2.6 — see status note)*
- ML governance and traceability at the experiment-platform level

### Should not become a main track in v3

- turning the project into a complete Databricks / Snowflake replacement
- introducing Kafka, Flink, or other complex distributed systems
- adding more business data sources or analytical features as a goal
- treating a complete online serving platform as a required v3 deliverable
- treating a self-service product UI or portal as a primary v3 deliverable

---

## Required capability areas

## 1. Infrastructure & Environment Promotion

### Goal

- support consistent deployment across environments
- establish a verifiable promotion chain
- guarantee that releases can be rolled back

### Requirements

- introduce Kubernetes manifests or a Helm chart skeleton
- introduce a Terraform baseline for infrastructure dependencies
- define the environment chain: `dev`, `staging`, `production`
- every promotion must pass:
  - successful deployment and health checks
  - successful pipeline execution
  - tests / lint / typecheck / runtime quality gates
  - rollback-readiness verification

### Note

The focus here is the **promotion model**, not simply adding `.env.dev` / `.env.prod` files.

---

## 2. Security & Access Governance

### Goal

- move from local-development credential handling to a production governance model

### Requirements

- progressively remove production dependence on static `.env` files
- introduce a managed secrets source and injection mechanism
- define least-privilege service credentials
- record audit evidence for access changes
- provide operating instructions for secrets rotation and emergency fallback

### Note

v3 focuses on **service-level security governance**, not on building a complete end-user authentication product first.

---

## 3. Reliability & Observability

### Goal

- move the system from "diagnosable" to "quantifiably operable"

### Requirements

- define the key SLOs
- establish metrics for the critical paths:
  - orchestration success rate
  - pipeline freshness
  - ingestion / pipeline latency
  - data quality pass rate
- establish alert rules aligned to SLO breaches
- provide a dashboard as the unified operational view
- complete incident runbooks and run at least a basic drill

### Note

Prometheus / Grafana are viable implementations, but v3 emphasizes **SLO-driven operations** rather than adopting tools for their own sake.

---

## 4. Data Governance Baseline

> Largely delivered in v2.6 — see the status note at the top of this document.

### Goal

- give critical datasets a discoverable, explainable, accountable governance baseline

### Requirements

- maintain the Hive-first catalog strategy *(v2.7 will evaluate an Iceberg REST catalog path; see the roadmap)*
- complete governance metadata for the critical Gold and core Silver datasets:
  - data owner
  - refresh SLA
  - quality class
  - lineage responsibility
- define cross-environment schema / table / storage-prefix naming conventions

### Note

The emphasis is **standardization and upgrade-readiness**.

---

## 5. ML Boundary for v3

### Goal

- keep narrative continuity from the data platform through to ML
- control scope so that serving does not expand prematurely

### Requirements

- strengthen reproducibility of training and evaluation
- strengthen experiment metadata, artifact lineage, and the evaluation contract
- keep MLflow as the core experiment-tracking component
- leave an interface open for future serving, without making a complete serving platform a v3 requirement

### Note

v3 is **experiment-platform first**, not full ML productization. See also ADR-011.

---

## 6. Release & Operations Model

### Goal

- move releases from "we can ship" to "controlled, auditable, and reversible"

### Requirements

- CI/CD continuously runs tests, lint, and type checks
- establish release gates
- establish a standard rollback procedure
- make release records and change evidence traceable
- update the release checklist, history, ADR index, and version status documents

---

## Explicitly not required for v3

- a complete online inference serving platform
- Superset / FastAPI as a core deliverable
- a full identity system at the Keycloak level
- mandatory DataHub adoption
- complex streaming architecture

These may be pursued as a later phase, as v4 candidates, or as separately scoped work driven by a concrete use case.

---

## Expected v3 outcome

SoloLakehouse v3 should present as:

> a small lakehouse platform reference implementation built with production thinking

It should have:

- reproducible multi-environment deployment
- an explicit environment promotion and rollback process
- a baseline of secrets, access, and governance controls
- SLO-driven observability and an operations baseline
- an auditable release process
- continuity of ML governance at the experiment-platform level

---

## v3 definition

> A production-capable, governance-ready, observable SoloLakehouse platform with controlled ML experiment integration.

---

## v3 task graph

This section is an implementation sequence, not a conceptual description.

### Workstream 1: Infrastructure Baseline

Goal: build the v3 skeleton so multi-environment deployment becomes an engineering object rather than a documentation goal.

- create Kubernetes manifests or a Helm chart skeleton
- design the deployment structure for the core services and Dagster
- define how `dev` and `staging` are layered
- introduce a Terraform baseline for infrastructure dependencies
- clarify how the local Compose path coexists with the v3 infrastructure path

Done when:

- the same version deploys to `dev` and `staging` from consistent artifacts
- deployment steps are reproducible, verifiable, and reversible

### Workstream 2: Promotion & Release Controls

Goal: turn releasing into a gated process rather than a one-off action.

- formalize the `dev -> staging -> production` promotion flow
- define the verification items for each promotion
- complete the rollback checklist and release evidence
- fold release checklist, history, ADR, and changelog updates into the process

Done when:

- at least one end-to-end staged release drill has been completed
- both promotion and rollback have documentation and verification records

### Workstream 3: Secrets & Access Governance

Goal: upgrade the v2 local-development credential model into a minimum production governance baseline.

- define the secrets source and runtime injection pattern
- identify credential boundaries for the critical services
- establish a least-privilege service credential model
- record audit requirements for access changes
- write rotation and emergency-fallback runbooks

Done when:

- critical services no longer depend on a static production `.env`
- access changes leave review and execution evidence

### Workstream 4: Observability & Reliability

Goal: move from "investigate after failure" to "monitor and warn proactively".

- define the key SLOs
- establish metrics for success rate, freshness, latency, and quality pass rate
- establish alerts and dashboards
- complete incident classification and recovery runbooks
- run at least a basic drill to validate the alerting and response chain

Done when:

- a minimum viable dashboard exists
- key alerts exist
- at least one runbook drill has been recorded

### Workstream 5: Data Governance Baseline

> Largely delivered by v2.6. v3 inherits and extends it across environments.

Goal: establish the governance conventions rather than rushing to change catalog systems.

- define governance contracts for the critical Gold and core Silver outputs
- complete data owner, refresh SLA, and quality class
- clarify lineage responsibility
- unify schema, table, and storage-prefix naming across environments

Done when:

- core datasets carry explicit governance metadata
- naming and ownership rules are directly followable by the team

### Workstream 6: ML Experiment Governance

Goal: continue the ML narrative while staying inside experiment-platform boundaries.

- strengthen reproducibility of training and evaluation
- unify experiment metadata and artifact path conventions
- define the evaluation contract
- leave an interface for future serving without implementing a serving platform

Done when:

- MLflow run records are more complete and traceable
- the relationship between model experiments and data assets is more explainable

---

## Recommended execution order

1. Infrastructure Baseline
2. Promotion & Release Controls
3. Secrets & Access Governance
4. Observability & Reliability
5. Data Governance Baseline *(mostly inherited from v2.6)*
6. ML Experiment Governance

The reasoning is straightforward:

- multi-environment deployment and a deployment skeleton must exist before governance and operations have anything to attach to
- release and rollback must be established before further change becomes controllable
- data and ML governance should sit on top of a stable platform skeleton

---

## For a code agent

A shorter version suitable for handing directly to a coding agent.

### SoloLakehouse v3 prompt

You are working on SoloLakehouse v3.

The project currently stands at:

- v1, v2, and v2.5 delivered (v2.5 is the protected runtime baseline)
- v2.6 delivered the governance and evidence plane
- v3 planned: production-capable platform hardening

Your job is to improve **platform productionization**, not to expand product features.

Priorities:

1. Multi-environment reproducibility
2. Promotion and rollback controls
3. Secrets and access governance
4. SLO-driven observability and incident operations
5. Extending the v2.6 governance baseline across environments
6. ML experiment governance, not full serving

Important constraints:

- do not expand scope into Kafka, Flink, or complex distributed systems
- do not treat FastAPI, Superset, or online serving as required v3 deliverables
- do not replace the current catalog baseline unless the roadmap says otherwise
- preserve compatibility with current v2 semantics where possible

Expected v3 outcome:

- reproducible deployment across environments
- a `dev -> staging -> production` promotion flow
- rollback readiness
- a managed secrets direction
- a least-privilege access baseline
- SLO-backed metrics, alerts, dashboards, and runbooks
- governance contracts applied consistently across environments
- stronger ML experiment lineage and reproducibility

When making decisions, prefer:

- maintainable patterns over maximal complexity
- governance clarity over tool-chasing
- upgrade-ready architecture over premature platform replacement
- production-minded operations over feature expansion

---

## One-line summary

> The goal of SoloLakehouse v3 is not to build more features, but to upgrade the existing platform into a production-capable reference implementation with multi-environment deployment, governance, security, observability, and release control.
