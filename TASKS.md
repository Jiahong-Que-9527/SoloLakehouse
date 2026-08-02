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

As of `2026-08-01`:

- `v2.5` is delivered and protected from regression.
- `v2.6.1` tag (`6bd138a`, `2026-07-31`) is **released** and carries the corrected
  version stamp. `v2.6.0` is superseded. The tag does **not** include Block `J`.
- Block `J` is **implemented and internally verified on `main`** (`e534c73`,
  PR #49). Independent external validation is deferred to the integrated
  post-v2.9 release gate.
- The active task is **v2.8 implementation**. Development then continues with
  v2.7 and v2.9 before external validation and operational rollout begin.
- `v2.8` before `v2.7` is an approved Owner Decision (`docs/roadmap.md`, D1).
- entity-template / entity-split work is **deferred indefinitely**
  (`docs/roadmap.md`, D2).

## Canonical Task Documents

| File | Role |
|---|---|
| `docs/roadmap.md` | **Authority** for what each version does |
| `TASKS.md` | **Authority** for what the next PR does |
| `task.md` | Design reference for entity deployment / migration — **not an active track** |
| `docs/history/v2.*-planning.md` | Superseded 2026-05-05 snapshots — context only, never instructions |

Rule:

- If the work is about **what the shared repository should implement next**,
  use `TASKS.md`.
- If any other document disagrees with `docs/roadmap.md` or `TASKS.md`, those
  two win.

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
| v2.6.0 | Superseded (version-stamp defect) | Computational governance and evidence plane |
| v2.6.1 | **Released — Block `J` implementation complete; external validation deferred until after v2.9** | Corrected version stamp; operationalize the evidence plane |
| v2.8 | **Active next development version** | AI/ML governance and agent-ready context |
| v2.7 | Planned — after v2.8 | Catalog/control-plane openness and sovereignty proof |
| v2.9 | Planned | Operational evidence and promotion discipline |
| v3.0 | Planned | Kubernetes runtime migration |

## Work Blocks

Historical block letters remain the stable map for planning references.

| Block | Theme | Primary versions | Current status |
|---|---|---|---|
| A | Dataset contracts and governed quality gates | v2.6 | Delivered |
| B | Promotion and rollback discipline | v2.9 | Planned |
| C | Observability and incident readiness | v2.9 | Planned |
| D | Secrets and access governance | v2.9 -> v3.0 | Planned |
| E | AI/ML governance and agent-ready context | v2.8 | Planned |
| F | Runtime productionization and K8s readiness | v2.9 -> v3.0 | Planned |
| G | Release governance and cross-version evidence packaging | v2.6 -> v3.0 | **External gate deferred to post-v2.9** |
| H | Lineage evidence and audit artifacts | v2.6 | Delivered |
| **J** | **Evidence-plane operationalization** | **v2.6.1** | **Implementation complete — external validation deferred to post-v2.9** |
| I | Catalog/control-plane openness and sovereignty proof | v2.7 | Planned |

## v2.6.1 Scope Boundary

`v2.6.1` Block `J` implementation is complete and internally verified.
Independent external validation and operational acceptance are deferred until
the integrated v2.9 release candidate; they do not pause v2.8, v2.7, or v2.9
development.

Its internal delivery succeeds when the evidence plane runs **without a human
in the loop**, on **every** governed dataset, into **write-once** storage.
Independent external verification is deferred to the post-v2.9 integrated gate.

### v2.6.1 must deliver

1. ~~`v2.6.1` is tagged and published with the corrected version stamp~~ — done
2. evidence is emitted automatically on successful materialization
3. the audit bucket cannot be silently overwritten
4. all five governed datasets are covered, not one
5. the three-source join verifies causality, not just name consistency
6. `governance/` and `dagster/` are inside the CI coverage gate

### v2.6.1 is explicitly not

- a new evidence category (that is v2.7 / v2.8)
- a Kubernetes, multi-engine, or streaming release
- a place to introduce policy enforcement (that is a v2.8 design question)

### Block R — Correct the released version stamp (do this first)

`v2.6.0` shipped on `2026-07-31` with `RUNTIME_VERSION` defaulting to
`slh-v2.5.1`. Every evidence manifest that release produces misattributes
itself to the previous runtime — on a release whose entire value proposition
is trustworthy evidence.

- [x] `R1` Fix `RUNTIME_VERSION` in `runtime_identity.py` and `.env.example`
- [x] `R2` Re-run the lineage-evidence drill and record it in
      `docs/v2.6-release-readiness.md` (run `43f859de…`, manifest
      `31e11d59…`, `runtime_version=slh-v2.6.0`)
- [x] `R3` Disclose the defect in the published `v2.6.0` release notes
- [x] `R4` Tag and publish `v2.6.1` carrying the fix

### Block J — Evidence-Plane Operationalization

Tasks `J1` and `J2` were in the original v2.6 plan (at 1 and 2 days) and were
dropped without being rescheduled. They are the difference between an evidence
plane that was demonstrated once and one that operates.

- [x] `J1` Dagster sensor emits lineage evidence automatically when a governed
      asset materializes successfully — removes the hand-copied run ID
      *(originally planned in v2.6 as the automatic Dagster hook, 1 day)*
- [x] `J2` Enable MinIO Object Lock on the audit bucket; document the retention
      mode actually configured and update the CHANGELOG limitation note
      *(originally v2.6 `E4`, 2 days)*
- [x] `J3` Extend evidence coverage to all five governed datasets
- [x] `J4` Bind snapshot to run causally: stamp `snapshot_id` into the Dagster
      asset materialization metadata and verify it in `LineageEvidenceJoiner`
      — today a stale snapshot plus an unrelated successful run yields a
      structurally valid record
- [x] `J5` Add `--cov=governance --cov=dagster` to the CI coverage gate
      (`.github/workflows/test.yml` currently covers only
      `ingestion`/`transformations`/`ml`, leaving the v2.6 centerpiece and the
      0%-covered Dagster layer unprotected)
- [x] `J6` Add unit tests for `dagster/assets.py` (currently 0% — 97 statements
      on the documented default execution path)

### Block G — Release Governance (deferred external gate)

- [x] `G3` Add an **external validation gate** to release readiness: at least one
      person outside the project runs `make setup` plus the integrated
      candidate's core commands on their own machine, and friction points are
      recorded
      *(gate + friction log: `docs/external-validation/`; execution deferred to
      the integrated post-v2.9 candidate)*
- [x] `G4` Confirm or overturn the provisional D1 ordering (v2.8 before v2.7)
      using the first round of external feedback, and record the outcome in
      `docs/roadmap.md`
      *(superseded by the 2026-08-02 Owner Decision: v2.8 first, then v2.7;
      external confirmation is deferred until after v2.9)*

## v2.6 — Delivered Scope (for reference)

`v2.6` implemented Blocks `A` (contracts + quality gates) and `H` (three-source
lineage evidence + audit manifest) in four waves. All `A1–A9`, `H1–H12`, `G1`,
and `G2` tasks are closed — see the block details below.

What v2.6 achieved:

- five machine-validated dataset contracts, enforced in CI
- a typed `LineageRecord` joining OpenMetadata, Iceberg, and Dagster by
  `dataset_id`, failing loudly rather than emitting partial evidence
- `make lineage-evidence` writing a SHA-256-bound manifest to a stable audit path
- one recorded real-environment drill for `fin.ecb_dax_features_gold`

What v2.6 did **not** achieve (now Block `J`, v2.6.1):

| Original v2.6 task | Estimate | Outcome |
|---|---|---|
| Dagster hook auto-writes evidence after the pipeline | 1 day | **Dropped, not rescheduled** → `J1` |
| `E4` MinIO Object Lock on the audit bucket | 2 days | **Dropped, not rescheduled** → `J2` |

Two further gaps were found during the 2026-07-31 architecture review and are
also in Block `J`: evidence covers only one of five governed datasets (`J3`),
and the three-source join verifies name consistency but not causality (`J4`).

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

- [x] `E1` Extend ML lineage beyond the current run metadata to a governed
      multi-part evidence tuple (`governance/ml_lineage.py`, ADR-018)
- [x] `E2` Add AI-governance fields and constraints on top of dataset contracts
- [x] `E3` Define agent-ready metadata and policy hooks without building a chat
      app (`governance/policy_hooks.py`, `make export-policy-hooks`)
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

- [x] `G1` Update release/readiness docs to include v2.6 evidence expectations
- [x] `G2` Add a v2.6 limitation note and change summary

### Block H — Lineage Evidence and Audit Artifacts

Scope:

- lineage record schema
- three-source lineage join
- evidence CLI
- audit artifact write path

Current v2.6 tasks:

- [x] `H1` Define `LineageRecord`
- [x] `H2` Define evidence output layout under the audit path
- [x] `H3` Implement OpenMetadata adapter
- [x] `H4` Implement Iceberg snapshot adapter
- [x] `H5` Implement Dagster run adapter
- [x] `H6` Join the three sources by `dataset_id`
- [x] `H7` Fail loudly when required source fields are missing
- [x] `H8` Add `make lineage-evidence`
- [x] `H9` Write manifest and evidence bundle output
- [x] `H10` Add tests for evidence generation and failure modes
- [x] `H11` Add stable audit-path naming rules
- [x] `H12` Record one lineage-evidence drill

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

Execute in this order.

1. **Implement v2.8** (`E1`–`E4`) with internal automated validation.
2. **Implement v2.7** (`I1`–`I5`) with internal automated validation.
3. **Implement v2.9** operational and promotion evidence.
4. **After v2.9 is complete, recruit an external validator** for the integrated
   v2.6.1–v2.9 candidate, retain the Block J protocol as a required evidence
   section, and record friction honestly.
5. **Start operational rollout only after that integrated sign-off**, then tag
   and publish the signed candidate and update planning state in the same PR.

## Decision Rules

- v2.8, v2.7, and v2.9 require their internal automated validation but are not
  blocked by external validation; external validation and operational rollout
  start after v2.9 completes
- do not add a new evidence category while the current one is manual,
  single-dataset, or overwritable
- do not hide missing source fields with best-effort partial outputs
- do not build chat or agent applications before metadata and policy hooks exist
- do not reopen entity-template preparation as the primary backlog without a new
  explicit roadmap decision (D2)
- do not treat engine count as a success metric
- do not commit customer-acquisition tooling (migration PoCs, TCO calculators)
  to this repository
- do not publish version dates; publish version order and current status

## Definition of "v2.6.1 Complete"

Distinguish the **released tag** from **Block `J` acceptance**:

| Milestone | Status | Evidence |
|---|---|---|
| Tag `v2.6.1` (version stamp fix) | **Done** | tag `6bd138a`, GitHub release `2026-07-31` |
| Block `J` implementation on `main` | **Done** | commit `e534c73`, PR #49, CI green |
| Block `J` operational acceptance | **Deferred to post-v2.9 integrated gate** | external sign-off + five-dataset audit record |

Block `J` counts as **externally accepted** as part of the post-v2.9 integrated
gate only when all are true:

- acceptance baseline is `e534c73` or later signed `main`
- a successful governed materialization produces evidence with **no** manual command
- the audit bucket has Object Lock enabled (fresh deploy or documented upgrade path)
- all five governed datasets produced audit manifests on the validator's machine
- the CI coverage gate includes `governance/` and `dagster/`
- at least one person **outside the project** signed
  `docs/external-validation/v2.6.1-external-validation.md`
- a **new** post-v2.9 tag is published (do not rewrite `v2.6.1` history)
