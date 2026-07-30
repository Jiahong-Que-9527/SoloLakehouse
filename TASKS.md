# SoloLakehouse Active Backlog

This file is the **single active backlog** for the shared SoloLakehouse
codebase.

Use it to answer:

- what the repository should build next
- which version is currently active
- what future agents must treat as in-scope or out-of-scope
- how v2.6 -> v3.0 work is sequenced

`docs/roadmap.md` defines the strategic direction.
`TASKS.md` defines the execution order and active backlog.

## Canonical Planning State

As of `2026-07-06`:

- `finlakehouse` acceptance is treated as complete.
- `v2.5` is delivered and protected from regression.
- the shared codebase must now advance `v2.6`.
- future agents should **not** reopen pre-split entity-template preparation as
  the main planning track unless a new regression or migration problem appears.

## Canonical Task Documents

| File | Role |
|---|---|
| `TASKS.md` | Active repository backlog and execution order |
| `task.md` | Entity deployment, side-by-side upgrade, and migration strategy |

Rule:

- If the work is about **what the shared repository should implement next**,
  use `TASKS.md`.
- If the work is about **how a product entity is deployed, upgraded, or
  migrated**, use `task.md`.

## Strategic Execution Rules

Future agents should follow these rules by default:

1. Prioritize **governance/control plane value** over adding engines.
2. Prefer **machine-executable metadata and evidence** over narrative-only docs.
3. Treat **agent readiness as a contract/policy/metadata problem first**.
4. Keep **v3 runtime migration** separate from `v2.x` governance work.
5. Do not regress the protected `v2.5` demo and pipeline path while adding new
   governance features.

## Current Version Focus

| Version | Status | Repository focus |
|---|---|---|
| v2.5 | Delivered / protected baseline | Protect from regression |
| v2.6 | Active next implementation | Computational governance and evidence plane |
| v2.7 | Planned | Catalog/control-plane openness and sovereignty proof |
| v2.8 | Planned | AI/ML governance and agent-ready context |
| v2.9 | Planned | Operational evidence and promotion discipline |
| v3.0 | Planned | Kubernetes runtime migration |

## Work Blocks

Historical block letters remain the stable map for planning references.

| Block | Theme | Primary versions | Current status |
|---|---|---|---|
| A | Dataset contracts and governed quality gates | v2.6 | Next |
| B | Promotion and rollback discipline | v2.9 | Planned |
| C | Observability and incident readiness | v2.9 | Planned |
| D | Secrets and access governance | v2.9 -> v3.0 | Planned |
| E | AI/ML governance and agent-ready context | v2.8 | Planned |
| F | Runtime productionization and K8s readiness | v2.9 -> v3.0 | Planned |
| G | Release governance and cross-version evidence packaging | v2.6 -> v3.0 | Planned |
| H | Lineage evidence and audit artifacts | v2.6 | Next |
| I | Catalog/control-plane openness and sovereignty proof | v2.7 | Planned |

## v2.6 Scope Boundary

`v2.6` is the current execution target.

It succeeds only when the repository can produce a governed evidence bundle for
at least one critical dataset from a stable operator command.

### v2.6 must deliver

1. dataset contracts exist and are machine-validated
2. critical quality gates are explicit and enforced
3. lineage evidence can be generated from three sources
4. evidence lands in a stable audit path with a manifest
5. governance metadata is ready for future purpose-based and AI/agent-safe use

### v2.6 is explicitly not

- a Kubernetes release
- a broad multi-engine demo release
- a streaming-platform expansion release
- a chat UI or agent app release
- a generic observability program

## Recommended v2.6 Implementation Order

The repository should implement `v2.6` in four waves.

### Wave 1: Contracts First

Goal:

- make governance metadata executable before evidence generation depends on it

Tasks:

- `A1` create `governance/datasets/*.yaml` for the critical datasets
- `A2` add schema validation for contract files
- `A3` define canonical contract fields:
  - `dataset_id`
  - `owner`
  - `business_purpose`
  - `refresh_sla`
  - `quality_class`
  - `consumers`
  - `retention`
  - `classification`
  - `source_of_truth`
  - `approved_consumer_class`
  - `access_policy_hint`
- `A4` add CI validation so missing required fields fail the build

Exit:

- the first governed Gold dataset and its critical upstream datasets have
  contracts
- the contract schema is machine-validated

### Wave 2: Evidence Model and Join Logic

Goal:

- turn distributed lineage signals into one stable in-repo evidence type

Tasks:

- `H1` define `LineageRecord`
- `H2` define evidence manifest shape and audit output layout
- `H3` build OpenMetadata adapter
- `H4` build Iceberg snapshot adapter
- `H5` build Dagster run adapter
- `H6` join the three sources by stable `dataset_id`
- `H7` fail loudly when required source fields are missing

Exit:

- one repository function can produce a complete structured lineage record

### Wave 3: CLI and Audit Writes

Goal:

- make evidence generation operational and repeatable

Tasks:

- `H8` add `make lineage-evidence DATASET=... DATE=...`
- `H9` write evidence to the configured audit path
- `H10` add a manifest suitable for signing and archiving
- `H11` add tests for success and missing-source failure paths

Exit:

- an operator can produce evidence with one command
- output naming and directory structure are stable

### Wave 4: Hardening and Drill

Goal:

- make the feature releasable rather than merely implemented

Tasks:

- `A5` add the minimum quality checks that governed datasets require
- `G1` update release/readiness docs for v2.6 evidence expectations
- `G2` record known limitations honestly
- `H12` record one lineage-evidence drill

Exit:

- `v2.6` is demonstrably runnable and auditable

## Block Details

### Block A — Dataset Contracts and Governed Quality Gates

Scope:

- contract registry
- contract schema validation
- critical dataset quality gates
- compatibility with `dataset-governance-naming.md`
- metadata fields that can later support purpose-based and AI/agent-safe access

Current v2.6 tasks:

- [x] `A1` Create `governance/datasets/fin.ecb_rates_bronze.yaml`
- [x] `A2` Create `governance/datasets/fin.dax_daily_bronze.yaml`
- [x] `A3` Create `governance/datasets/fin.ecb_rates_silver.yaml`
- [x] `A4` Create `governance/datasets/fin.dax_daily_silver.yaml`
- [x] `A5` Create `governance/datasets/fin.ecb_dax_features_gold.yaml`
- [x] `A6` Add a Pydantic schema for dataset contracts
- [x] `A7` Add a validation command for contracts
- [x] `A8` Wire contract validation into CI
- [x] `A9` Add the minimum governed-dataset quality gates

### Block B — Promotion and Rollback Discipline

Scope:

- promotion evidence
- rollback commands
- rollback drills

Status:

- deferred to `v2.9`

### Block C — Observability and Incident Readiness

Scope:

- SLO metrics
- breach handling
- incident evidence

Status:

- deferred to `v2.9`

### Block D — Secrets and Access Governance

Scope:

- secrets discipline
- least privilege
- rotation evidence

Status:

- deferred to `v2.9 -> v3.0`

### Block E — AI/ML Governance and Agent-Ready Context

Scope:

- ML lineage binding
- model/evaluation evidence
- AI asset governance
- policy-ready metadata for future MCP or agent consumption

Planned v2.8 tasks:

- [ ] `E1` Extend ML lineage beyond the current run metadata to a governed
      multi-part evidence tuple
- [ ] `E2` Add AI-governance fields and constraints on top of dataset contracts
- [ ] `E3` Define agent-ready metadata and policy hooks without building a chat
      app
- [ ] `E4` Generate model/evaluation evidence aligned with the project’s EU AI
      Act traceability goals

### Block F — Runtime Productionization and K8s Readiness

Scope:

- Kubernetes readiness checks
- runtime migration preparation

Status:

- deferred to `v2.9 -> v3.0`

### Block G — Release Governance and Evidence Packaging

Scope:

- release evidence
- carried-forward documentation
- readiness gate updates

Current v2.6 tasks:

- [ ] `G1` Update release/readiness docs to include v2.6 evidence expectations
- [ ] `G2` Add a v2.6 limitation note and change summary

### Block H — Lineage Evidence and Audit Artifacts

Scope:

- lineage record schema
- three-source lineage join
- evidence CLI
- audit artifact write path

Current v2.6 tasks:

- [x] `H1` Define `LineageRecord`
- [x] `H2` Define evidence output layout under the audit path
- [ ] `H3` Implement OpenMetadata adapter
- [ ] `H4` Implement Iceberg snapshot adapter
- [ ] `H5` Implement Dagster run adapter
- [ ] `H6` Join the three sources by `dataset_id`
- [ ] `H7` Fail loudly when required source fields are missing
- [ ] `H8` Add `make lineage-evidence`
- [ ] `H9` Write manifest and evidence bundle output
- [ ] `H10` Add tests for evidence generation and failure modes
- [ ] `H11` Add stable audit-path naming rules
- [ ] `H12` Record one lineage-evidence drill

### Block I — Catalog/Control-Plane Openness and Sovereignty Proof

Scope:

- catalog abstraction boundary
- Iceberg REST catalog compatibility
- Apache Polaris reference path
- minimal interoperability proof
- sovereignty report and exit playbook

Planned v2.7 tasks:

- [ ] `I1` Define the repository-level catalog abstraction boundary
- [ ] `I2` Document the current HiveCatalog path versus Iceberg REST catalog path
- [ ] `I3` Evaluate Apache Polaris as the first reference REST catalog target
- [ ] `I4` Produce one minimal interoperability proof after the catalog boundary
      is explicit
- [ ] `I5` Write the sovereignty report and exit playbook

Rule:

- do not treat engine count as the main success metric for `v2.7`

## Immediate Next Actions

If implementation resumes now, do these in order:

1. create the contract schema and first contract files
2. decide the exact `LineageRecord` and manifest fields
3. implement adapters and test fixtures before wiring the CLI
4. add the operator command and audit writes
5. only then start the `v2.7` catalog-boundary work

## Decision Rules

- do not start `v2.7` implementation before `v2.6` has a usable evidence CLI
- do not widen `v2.6` into a generic observability or platform-expansion track
- do not hide missing source fields with best-effort partial outputs
- do not build chat or agent applications before metadata and policy hooks exist
- do not reopen entity-template preparation as the primary backlog without a new
  explicit roadmap decision

## Definition of "v2.6 Started"

`v2.6` counts as implementation-started only when all are true:

- at least one contract file exists in `governance/datasets/`
- a machine-validated contract schema exists
- `LineageRecord` exists in code
- there is an active branch or merged commit implementing Block `A` or `H`

Until then, `v2.6` remains planning rather than implementation.
