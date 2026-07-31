# Roadmap

> **Authority.** This document defines **what each version does**. `TASKS.md`
> defines **what the next PR does**. When any other document in this repository
> disagrees with these two, these two win. The v2.6–v2.9 version planning notes
> are superseded `2026-05-05` snapshots, kept locally and not published; this
> document supersedes them.

SoloLakehouse evolves along a single path — the runtime stays on Docker Compose
until v3.0, and each v2.x version adds **one category of evidence**:

```text
v2.5  the platform runs
  -> v2.6   the platform produces evidence
     -> v2.6.1  that evidence is operational, not just demonstrable
        -> v2.7 / v2.8  openness evidence  OR  auditable-AI evidence  (order undecided)
           -> v2.9  operational and promotion evidence
              -> v3.0  the runtime migrates to Kubernetes
```

## Primary Audience

The primary audience is **technical decision-makers in EU/DACH financial and
regulated data organizations** — people who must answer to auditors and
regulators.

When depth and breadth conflict, **depth wins**: one capability that is
automated, enforced, and honestly bounded beats three that are demonstrable
once. Portfolio and hiring visibility is a valued by-product of that depth, not
a design goal that competes with it.

## Current Strategic Position

As of `2026-07-31`:

- `v2.5` remains the protected baseline runtime and does not change until v3.0.
- `v2.6.1` is **released** (tagged `2026-07-31`) and is the current version.
- `v2.6.0` is **superseded**: it stamped `slh-v2.5.1` into every evidence
  manifest. Anyone on that tag should upgrade and regenerate their evidence.
- the next implementation focus is **`v2.6.1`** — deepen the evidence plane
  before adding a new evidence category.
- `v2.7` vs `v2.8` ordering is an **open decision**; see "Open Decisions" below.
- future planning prioritizes **control plane and evidence value** over adding
  more engines or surface features.

## Version Status

| Version | Status | Theme |
|---------|--------|-------|
| v1.0 | Delivered (historical) | Runnable lakehouse baseline |
| v2.0 | Delivered (historical) | Dagster orchestration introduction |
| v2.5 | Delivered / protected baseline | Single-track all-layer Iceberg runtime + Dagster + Trino + MLflow + OpenMetadata + Superset |
| v2.6.0 | Superseded — carries a version-stamp defect | Computational governance and evidence plane |
| v2.6.1 | **Released `2026-07-31` — current** | Corrected version stamp; English-only publication; unified agent entry points |
| v2.6.1 Block `J` | **Active next implementation** | Operationalize the evidence plane |
| v2.7 | Planned (order undecided) | Catalog/control-plane openness and sovereignty proof |
| v2.8 | Planned (order undecided) | AI/ML governance and agent-ready context |
| v2.9 | Planned | Operational evidence and promotion discipline |
| v3.0 | Planned | Production runtime migration to Kubernetes |
| v4.0 | Future candidate | Self-serve usability and operational clarity |

## Delivery Velocity (measured, not estimated)

Plan with the **measured** rate, not the optimistic one:

| Version | Planned | Actual | Ratio |
|---|---|---|---|
| v2.6 (`2026-05-10` → `2026-07-31`) | 4 weeks | **11.7 weeks** | **≈ 2.9×** |

Rules that follow from this:

- Multiply every remaining estimate by **≈3** before committing to a date.
- At the measured rate, v3.0 lands in **early 2028**. Any plan that assumes
  v3.0 in 2026 or 2027 is invalid.
- Do not publish version dates. Publish version **order** and current status.
- The `M1–M4` six-month milestone plan in the local-only enterprise evolution
  note (2026-05-05) is **superseded** — M1 alone consumed both quarters it
  allotted for M1 and M2.

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

### v2.6.1 — Operationalize the Evidence Plane

Primary outcome:

- the evidence plane runs **without a human in the loop**, on **every** governed
  dataset, into **write-once** storage

Why this version exists:

`v2.6` shipped roughly 80% of its plan. The 20% that did not ship is exactly the
part that separates *demonstrable* from *operational*, and it was never
rescheduled into any later version. Adding a second evidence category (v2.7 or
v2.8) on top of a manually-triggered, single-dataset, overwritable evidence
plane would compound that gap rather than close it.

Core deliverables:

- ~~Correct the `v2.6.0` version stamp~~ — **shipped in `v2.6.1`**. The drill
  was re-run and the manifest read back to confirm `runtime_version=slh-v2.6.1`.
- Automatic evidence emission: a Dagster sensor generates evidence when a
  governed asset materializes successfully — no hand-copied run IDs.
  *(Was in the v2.6 plan at 1 day; dropped.)*
- WORM audit storage: enable MinIO Object Lock on the audit bucket so archived
  evidence cannot be silently overwritten or deleted.
  *(Was in the v2.6 plan as E4 at 2 days; dropped.)*
- Coverage for **all** governed datasets, not only `fin.ecb_dax_features_gold`.
- **Causal** snapshot↔run binding: today the three-source join verifies name
  consistency but not causality — a stale Iceberg snapshot plus an unrelated
  successful Dagster run produces a structurally valid record. Stamp the
  snapshot ID into the asset materialization and verify it on join.
- CI coverage gate extended to `governance/` and `dagster/` (currently excluded,
  so the v2.6 centerpiece has no regression protection).

Important framing:

- `v2.6.1` adds **no new evidence category**. It makes the existing one true.
- Only after this is `"the platform produces evidence"` a claim about the
  platform rather than about one recorded drill.

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

Known precondition (code, not documentation):

- `ingestion/iceberg_io.py:get_catalog()` constructs `HiveCatalog`
  unconditionally, and `governance/lineage.py:OpenMetadataAdapter` hard-codes the
  four-segment Trino FQN shape. There is currently **no** point in the codebase
  where a catalog backend can be selected. The first v2.7 change must be a small
  refactor that creates those seams — otherwise "catalog-independent" is a claim
  the code contradicts.

Scope reduction from the 2026-05-05 planning note:

The superseded note budgeted 30 days, of which ~17 went to work this roadmap
does not endorse. Dropped or downgraded: Spark demo (4d), Flink streaming demo
(5d), `migrate-from-databricks.py` (5d — sales PoC tooling, not platform
capability), cross-object-store demo (3d). Retained: sovereignty report,
portability matrix, DuckDB read (near-zero cost via pyiceberg), REST catalog
switch, exit playbook, plus the catalog abstraction seam above.

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

Corrected timing rationale:

The superseded planning note justified v2.8's priority by aligning it with the
EU AI Act high-risk obligations date of `2026-08-02`. **That window has passed
and cannot be met** — at the measured velocity v2.8 is 6–12 months out under any
ordering. v2.8's value must stand on the durable argument instead: traceability
from model to dataset to snapshot to run to contract is required by regulated
model governance regardless of any single regulatory date.

Known gap to design before starting:

- `approved_consumer_class` and `access_policy_hint` exist in the contract schema
  but nothing enforces them — any credentialed Trino user can read a governed
  table today. If "agent-ready policy hooks" is to mean anything, the hard part
  is a **policy enforcement point** (Trino access-control provider, or a proxy in
  front of MCP-style tool calls), not more contract fields. Decide that approach
  before writing E1–E4.

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
- v3.0 is an **infrastructure** milestone, not a narrative one. It is explicitly
  **not** a gate for talking about the project publicly — see "External
  Validation" below.

## Open Decisions

Decisions recorded here are open until this section says otherwise. Agents must
not start implementation work that depends on an open decision.

### D1 — v2.7 before v2.8, or v2.8 before v2.7?

**Status: provisionally decided — v2.8 first. Confirm with external input before
implementation starts.**

The provisional direction is **v2.8 (AI/ML governance) before v2.7 (catalog
openness)**, on the dependency argument below. This is recorded so v2.6.1 work
is not blocked, but it is not final: the first round of external feedback after
the v2.6.0 release should either confirm it or overturn it. Whichever way it
lands, record the outcome here and close `G4`.

| | Reuse of v2.6 machinery | Standalone timing pressure | Scope |
|---|---|---|---|
| **v2.8** (AI/ML governance) | **High** — the lineage five-tuple extends the existing contracts, lineage join, and audit bucket directly | AI-governance interest is current; the specific `2026-08-02` anchor is already missed | ~23 planned days |
| **v2.7** (openness/sovereignty) | **Low** — the sovereignty report scans compose files; the multi-engine proof is independent of v2.6 code | Vendor lock-in concern is evergreen, not time-boxed | ~13 days after the scope reduction above |

The dependency argument favors **v2.8 first** — two consecutive versions
deepening one governance mechanism, with the ML lineage tuple extending the
contracts, lineage join, and audit bucket that v2.6.1 will have just made
operational. The lower-cost argument favors **v2.7 first**.

The provisional decision follows the dependency argument. What would overturn
it: external readers consistently asking about vendor lock-in and catalog
portability rather than model traceability. That signal is worth more than this
reasoning — collect it before committing.

### D2 — Entity split (`task.md`)

**Status: deferred indefinitely.** `task.md` describes splitting this codebase
into `finlakehouse` and `aviation-lakehouse` product entities. That track is a
**design reference, not an active plan**. Its Phase-2+ checklists are not part of
any version above. Do not reopen it as a primary backlog without an explicit
decision recorded here.

### D3 — Portal / Keycloak exploration

**Status: sandbox only.** Local `.env` carries `KEYCLOAK_*` and `PORTAL_OIDC_*`
values for an exploratory self-service portal. `docs/v3-spec.md` explicitly lists
a self-service portal as out of scope for v3.0. Until this decision changes, that
work is a personal sandbox: it must not enter `docker/docker-compose.yml`,
`.env.example`, or any version scope above.

## External Validation

Every acceptance gate in this project's history has been self-certified. The
repository has been public since `2026-03-25` and has accumulated 55 stars with
zero external issues, pull requests, or discussions — meaning people find it
credible enough to bookmark but have not crossed the threshold to run it. That
is an activation problem, not an awareness problem.

Therefore, from v2.6.0 onward:

- **Every release requires at least one person outside the project** to run
  `make setup` plus that version's core command on their own machine, with
  friction points recorded. This is a release-readiness gate, not a nice-to-have.
- **Releases are the outreach cadence.** Ship the release, publish one short
  technical note about the single most differentiated thing in it, and ask a
  specific question of 8–10 target readers. Budget ~2 days per version, not a
  separate "operations phase".
- **There is no version at which outreach begins.** Waiting for v3.0 would mean
  ~19 months of compounding unvalidated assumptions before the first external
  signal. The evidence plane delivered in v2.6 is already the most
  differentiated claim this project has.

## What Is Explicitly Deprioritized

These items may happen later, but they are not primary success criteria now:

- opening a second major domain track before the current governance path is
  fully established
- broad streaming expansion without a concrete governed use case
- replacing MinIO purely for novelty
- building chat UI or agent apps before governance and policy primitives are in
  place
- using Spark/dbt/Flink adoption as a proxy for platform maturity
- **adding a new evidence category while the previous one is still manual,
  single-dataset, or overwritable** (this is what v2.6.1 exists to prevent)
- **customer-acquisition tooling** (migration PoCs, TCO calculators, proposal
  generators) — these belong to a commercial track, not to a reference
  implementation's roadmap

## History References

For historical context and retired planning material:

- [history/timeline.md](history/timeline.md)
- [history/architecture-evolution.md](history/architecture-evolution.md)
- [history/legacy-overview.md](history/legacy-overview.md)

### Superseded planning material

These documents are **historical snapshots**. They are kept because they record
what was believed at the time, and they are cross-linked from the timeline. They
are **not** instructions, and where they conflict with this roadmap, this
roadmap wins.

| Document | Written | Superseded because |
|---|---|---|
| `history/v2.6-planning.md` *(local-only)* | 2026-05-05 | Delivered; two planned items (auto-emission, WORM) moved to v2.6.1 |
| `history/v2.7-planning.md` *(local-only)* | 2026-05-05 | Makes a 4-engine demo the primary acceptance gate, which this roadmap rejects; ~17 days of scope dropped |
| `history/v2.8-planning.md` *(local-only)* | 2026-05-05 | Its timing rationale (EU AI Act `2026-08-02`) has passed |
| `history/v2.9-planning.md` *(local-only)* | 2026-05-05 | Written before v2.6 shipped; assumes the superseded milestone plan |
| Enterprise evolution note *(local-only)* | 2026-05-05 | `P1–P5` framing remains useful; the `M1–M4` six-month milestone plan is invalid |

All four v2.x planning notes were written on a single day (`2026-05-05`), before
v2.6 implementation began. Specifying three future versions in task-level detail
ahead of shipping the first one is the pattern this roadmap now avoids: plan the
**next** version in detail, and the ones after it only as direction.
