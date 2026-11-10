# Active work

[Roadmap](docs/roadmap.md) owns scope. This file owns the execution order.
[Construction plan](docs/design/v3/README.md) owns detailed design within that
scope. Do not maintain parallel active queues in archived specifications.

## Current stage

**D0 repository preparation is merged; D1.1 construction-input decisions are
next and not yet implemented.** The framework landed in PR #100; PRs #101 and
#102 added the architecture diagram and platform cover. Hardware is not
provisioned. Infra/bootstrap/deploy/gitops still contain responsibility documents,
not Terraform resources, Ansible plays, Helm charts or Flux manifests.

## Start here in the next session

Read [AGENTS](AGENTS.md), [roadmap](docs/roadmap.md), this file and only the
relevant [construction-plan section](docs/design/v3/README.md). The default
next output is **D1.1: a construction-input decision record, sanitized example
specification, and the scope/acceptance commands for one VM definition**.
Start with existing evidence and leave unverified inputs explicitly open.
Recording this queue does not implement or authorize every listed operation.

Use the stable IDs below in branches/PRs and handoffs. After a bounded change,
update its checkbox only when its acceptance evidence exists; record the
commit/PR, commands/results, remaining gaps and next ID here in the same PR.
Update roadmap/design only when scope, state or a decision changes. Keep this
as the sole active queue; tool entrypoints and GitHub issues must link here
rather than maintain competing copies.

Source baseline: a1bef2e on v3/development.
The [archive](docs/history/pre-v3/README.md) preserves original entry documents
and six older planning documents, with hashes and source commit.
The earlier pre-v3 tag preserves main at 2d8020a; it does not include later
preparation changes. Obsolete branch cleanup was independently verified.

## D0 deliverables already merged

| Deliverable | Boundary |
|---|---|
| README and reading route | Existing implementation and planned v3 explicitly separated |
| Complete construction plan | Resource, network, storage/recovery, delivery, environments, migration and validation |
| Monorepo scaffold | Responsibility READMEs; no pretend executable deployment |
| Archive and retained-work ledger | Original bytes/signatures plus every old unchecked item's provenance |
| Safe commands and checks | No general Make target destroys data; scoped documentation/integrity checks |
| Validation record | Actual check results in the PR; no hardware/Compose acceptance inferred |

Completion of repository work does not complete later construction stages.

## Next bounded work

All items below are pending. D1.1 comes first. After their own inputs are ready,
D1.2 and D1.3 may proceed independently; an S3 choice does not block a VM
definition. D1.4 follows the cluster/delivery decisions. Hardware-dependent
acceptance remains H0 onward.

- [ ] **D1.1 — resolve construction inputs.** Next session; see the detailed
  inputs and acceptance below.
- [ ] **D1.2 — isolated S3 compatibility slice.** Validate candidate image
  supply, PyIceberg writes/reads, Trino queries, MLflow artifacts and current
  evidence/Object Lock semantics with fixture data. Output: repeatable results,
  explicit unsupported behavior, selection and rollback decision. Preserve the
  reference store. Requires a separately scoped isolated runtime environment.
- [ ] **D1.3 — first static VM/bootstrap slice.** After the relevant D1.1
  inputs, implement one reusable PVE guest definition under infra/proxmox plus
  cloud-init inputs under bootstrap/cloud-init. Specify CPU/RAM/disks/network,
  trusted SSH inputs, guest integration and state ownership. Provide sanitized
  examples and format/validate/schema checks against actual files. No apply,
  host installation or claim that a VM boots; three-host expansion follows
  actual single-guest validation.
- [ ] **D1.4 — minimal GitOps configuration slice.** After cluster, network,
  identity and secret-recovery decisions, implement Flux entry/dependencies and
  validation/stable configuration for one stateless test app. Output: pinned
  sources/images, render/schema validation and documented promotion/rollback
  commands. Keep pruning/deletion behavior explicit; runtime reconciliation,
  drift correction and rollback remain H2 acceptance.
- [ ] **H0 — hardware and PVE acceptance.** Await machines and an explicit
  operational scope. Output: actual inventory, RAM/SSD/NIC/thermal/power-return
  and link results, three-host PVE/quorum baseline and backup-path evidence.
- [ ] **H1 — reproducible K3s cluster.** Provision one guest per physical
  host from validated definitions; configure K3s and stable API access. Output:
  guest rebuild, etcd/quorum health, controlled one-host outage behavior,
  degraded capacity and isolated snapshot/token recovery evidence.
- [ ] **H2 — GitOps test application.** Bootstrap Flux with independently
  recoverable Git/decryption inputs. Demonstrate reviewed release, drift
  correction and compatible rollback before deploying important state.
- [ ] **W0 — fixture finance migration and first consistent restore.**
  Requires S3 selection/compatibility and H2. Preserve source/dataset semantics;
  validate persistent stores/catalog, Trino, Dagster Job, Iceberg/Gold/query and
  evidence, followed by isolated catalog+object recovery before important state.
- [ ] **W1 — capability parity.** Regress approved finance sources, quality,
  lineage, metadata, MLflow and BI independently. Enable only intended schedules
  after controlled fixture acceptance; keep operated fin/avi environments separate.
- [ ] **O0 — operational acceptance.** Measure resource/load/freshness and
  failure behavior; define SLOs from a baseline, rehearse isolated rollback and
  recovery, and report observed RPO/RTO against selected objectives and limits.

The [migration and validation plan](docs/design/v3/migration-and-validation.md)
owns detailed stage procedures and rollback boundaries. Relevant retained work
below must be reconciled within these stages, not discarded by renumbering.

## D1.1 inputs and acceptance

| Input | Work to record | Acceptance / destination |
|---|---|---|
| Network and procurement | Inspect existing LAN, VPN/Tailscale, container and candidate Pod/Service ranges; assign naming, VLAN/CIDR intent, API/ingress ownership and switch port/speed/VLAN needs | Evidence-backed overlap matrix and switch requirements in architecture; actual addresses/inventory stay private |
| Versions and capacity | Select compatible PVE, guest OS, K3s, OpenTofu/provider and bootstrap inputs using current official sources; account for host reserve, one 24GiB guest per 32GB host and disk headroom | Dated compatibility/source record, upgrade/rollback assumptions and measurable resource budget; estimates labeled |
| Storage and backup | Confirm NAS protocol/export/access and expected throughput; define local PVC placement, consistency boundaries, retention, independent/offsite copies and restore order | Storage/recovery amendment; distinguish proposed objectives from measured RPO/RTO and untested restore |
| State, credentials and recovery | Decide OpenTofu state/lock/single-writer ownership, Git/Flux credentials, SOPS/age keys, K3s token/snapshots and external admin environment | Public/encrypted/local-only classification plus independent recovery locations/procedure; no live secret or actual inventory committed |
| First implementation contract | Specify one guest's variables, sanitized examples, manual PVE prerequisites and applicable static checks | Bounded D1.3 file scope and acceptance commands; unresolved inputs identified rather than executable guesses |

Deliver the decision record as amendments to
[architecture](docs/design/v3/architecture.md),
[storage/recovery](docs/design/v3/storage-and-recovery.md) and
[delivery/environments](docs/design/v3/delivery-and-environments.md).
Provide sanitized example specifications where useful; executable examples
belong to the corresponding implemented slice. Record alternatives and rollback
when choosing a dependency; use an ADR for a material new architectural choice.

**D1.1 exit:** each input is decided with a source/date and validation method,
or explicitly open with its dependent slice blocked. Document the first VM
implementation scope and commands; do not mark D1.1 complete merely for listing
questions. No current version choice, address allocation, NAS export or recovery
success is implied by this task record.

## Handoff record

Latest completed repository work: D0 framework (#100), architecture diagram
(#101) and platform cover (#102). This follow-up records future work and agent
navigation only. **Next: D1.1.** No D1 implementation or hardware/runtime result
has been produced. Repository validation for this handoff: `make docs-check
check-agent-docs` passed (234 local links, 34 unchanged archived originals,
32 prior unchecked items accounted for, five shared agent entrypoints);
`git diff --check` passed. GitHub CI results are attached to the delivery PR.
Later completion entries must include actual evidence and replace this
next-action statement when the queue advances.

## Retained work

The [retained-work ledger](docs/design/v3/retained-work.md) is the provenance
index for **every unchecked item** in the prior 902-line TASKS snapshot.
Do not interpret its historical text as a second execution queue.

| Retained work | Treatment |
|---|---|
| K2 version consistency | Revalidate actual runtime/image stamps; do not infer closure from unrelated lineage fixes |
| K4-K8 concurrency, disk/freshness/health, secret-bearing config | Carry into the relevant v3 runtime/operational slice; not implemented by D0 |
| K9/K10 backup and restore | Design now; first real isolated restore before important state; no current runtime success claim |
| K11-K14 security/restart/write/backup ADRs | Retain missing rationale. Historical “next ADR-024” was a placeholder; 024 now identifies the monorepo decision, not closure of these tasks |
| K15-K17 JDBC pinning, Iceberg lifecycle, schema evolution | Retain; lifecycle/destructive work requires explicit state scope |
| D6 aviation case and observed gaps | Still unfinished where not evidenced; separate implementation/privacy boundaries preserved |
| Reference cold-clone/image supply | Still open; fixture/static checks are not a fresh Compose demo |
| L4 crypto phase 2 and related subitems | Deferred; no Redpanda/Kafka/new-domain implementation |
| Stale PR #81 merge checkbox | Historical mismatch: PR #81 was merged. Preserve original checkbox but do not reactivate the merge task |

The legacy DAX dataset contracts and Python names are still referenced.
A later rename requires its own compatibility change; no broad code deletion
is authorized by documentation cleanup.

## Execution rules

- Work one bounded slice with a stated output and verification method.
- Preserve existing code/data contracts, reference paths, authentic history and
  unresolved tasks. Do not turn a plan or old verification into current proof.
- No new service, target-host operation or existing fin/avi migration follows
  automatically from this design.
- Use fixture or isolated state for validation; keep final consumed model test
  data and real operated data outside exploratory reruns.
- Before substantial edits preserve a current recoverable snapshot. Data
  deletion/disposal requires exact targets and approval; generic clean/reset
  commands are not an approved recovery procedure.
