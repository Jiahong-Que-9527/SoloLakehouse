# Roadmap

SoloLakehouse now has a single active execution path:

```text
finlakehouse acceptance complete
  -> strengthen the governance and evidence plane on the existing runtime
     -> prove openness through catalog and interoperability boundaries
        -> extend governance to AI and agent-ready context
           -> harden operational evidence
              -> migrate the runtime to Kubernetes
```

This document and `TASKS.md` are the canonical planning sources for the shared
codebase.

## Current Strategic Position

As of `2026-07-31`:

- `finlakehouse` deployment validation is treated as complete.
- `v2.5` remains the protected baseline runtime.
- `v2.6` governance-evidence release validation is complete.
- the next implementation focus is `v2.7`.
- future planning should prioritize **control plane and evidence value** over
  adding more engines or surface features.

## Version Status

| Version | Status | Theme |
|---------|--------|-------|
| v1.0 | Delivered (historical) | Runnable lakehouse baseline |
| v2.0 | Delivered (historical) | Dagster orchestration introduction |
| v2.5 | Delivered / protected baseline | Single-track all-layer Iceberg runtime + Dagster + Trino + MLflow + OpenMetadata + Superset |
| v2.6 | Delivered | Computational governance and evidence plane |
| v2.7 | Active next implementation | Catalog/control-plane openness and sovereignty proof |
| v2.8 | Planned | AI/ML governance and agent-ready context |
| v2.9 | Planned | Operational evidence and promotion discipline |
| v3.0 | Planned | Production runtime migration to Kubernetes |
| v4.0 | Future candidate | Self-serve usability and operational clarity |

## Strategic Alignment Rules

These rules are the default planning lens for future work:

1. **Prefer control plane value over engine count.**
   Success is not measured by how many compute engines are attached. It is
   measured by whether catalog, lineage, access control boundaries, and audit
   evidence are explicit and portable.

2. **Prefer executable governance over narrative governance.**
   Contracts, quality gates, lineage records, manifests, and audit outputs
   should be machine-readable and testable.

3. **Treat agent readiness as a metadata and policy problem first.**
   SoloLakehouse should become a governed context layer that future AI agents
   can consume safely. It should not prioritize building chat apps or a full
   agent product before governance primitives exist.

4. **Keep v3 runtime migration separate from v2.x evidence work.**
   Kubernetes, Helm, Terraform, secrets lifecycle, and promotion models belong
   in the runtime migration track only after the governance and evidence claims
   are already provable on the current stack.

## Current Baseline (v2.5)

The protected v2.5 baseline includes:

- Dagster as the only orchestration engine
- all three medallion layers written as Iceberg tables via `pyiceberg`
- Trino as the shared SQL/query surface
- OpenMetadata in the default platform stack
- Superset in the default platform stack
- MLflow experiment tracking on the same runtime
- `make demo` as the acceptance/demo path
- `make pipeline` as the full pipeline path including MLflow execution

Operational contract:

- `make setup` prepares a cold clone and starts the mandatory stack
- `make up` restarts the stack after setup
- `make verify` validates services and UIs
- `make demo` executes the demo data flow
- `make pipeline` executes the full pipeline

Future work must not regress this baseline without an explicit roadmap change.

## Version-by-Version Direction

### v2.6 — Computational Governance and Evidence Plane

Primary outcome:

- one governed dataset can produce a structured, archivable, repeatable evidence
  bundle from repository-native commands

Core deliverables:

- machine-validated dataset contracts
- governed quality gates for critical datasets
- typed lineage record and three-source lineage join
- evidence CLI and stable audit manifest layout
- release/readiness evidence for the new governance path

Important framing:

- `v2.6` is not a general observability or platform expansion release
- `v2.6` should prepare future purpose-based access and AI/agent consumption by
  making governance metadata executable now
- the external demonstration goal is defined in
  [v2.6-demo-goal.md](v2.6-demo-goal.md)

### v2.7 — Catalog/Control-Plane Openness and Sovereignty Proof

Primary outcome:

- the platform can demonstrate that governance identity and table access do not
  depend on a single catalog implementation or vendor path

Core deliverables:

- explicit catalog abstraction boundary
- Iceberg REST catalog compatibility path
- Apache Polaris evaluation as the first reference implementation
- minimal multi-engine proof after the catalog boundary is clear
- sovereignty report and exit playbook

Important framing:

- catalog/control-plane portability comes before adding more engines
- engine count is not a success metric on its own

### v2.8 — AI/ML Governance and Agent-Ready Context

Primary outcome:

- AI and ML assets can be traced back to governed datasets, runs, contracts, and
  policy context

Core deliverables:

- ML lineage binding across dataset, snapshot, run, code, and contract metadata
- AI governance extensions on top of the v2.6 contract/evidence plane
- agent-ready metadata and policy hooks for future MCP-style consumption
- model/evaluation evidence aligned with EU AI Act-style traceability goals

Important framing:

- this version should strengthen governance primitives for AI
- it should not expand into a full conversational agent application platform

### v2.9 — Operational Evidence and Promotion Discipline

Primary outcome:

- the platform can demonstrate repeatable operations, rollback readiness, and
  promotion discipline on the existing runtime

Core deliverables:

- SLO-oriented operational evidence
- rollback and drill artifacts
- secrets/access discipline documentation and checks
- readiness gates for the runtime migration

### v3.0 — Production Runtime Migration

Primary outcome:

- the same platform contracts run across multiple environments on Kubernetes

Core deliverables:

- Kubernetes deployment baseline
- Helm packaging
- Terraform infrastructure baseline
- environment promotion model
- managed secrets path

Important framing:

- v3.0 is a runtime migration release, not the place to introduce the core
  governance concepts for the first time

## What Is Explicitly Deprioritized

These items may happen later, but they are not primary success criteria now:

- opening a second major domain track before the current governance path is
  fully established
- broad streaming expansion without a concrete governed use case
- replacing MinIO purely for novelty
- building chat UI or agent apps before governance and policy primitives are in
  place
- using Spark/dbt/Flink adoption as a proxy for platform maturity

## History References

For historical context and retired planning material:

- [history/timeline.md](history/timeline.md)
- [history/architecture-evolution.md](history/architecture-evolution.md)
- [history/legacy-overview.md](history/legacy-overview.md)
