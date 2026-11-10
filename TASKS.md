<!-- [房玄龄·2026-11-10] Owner-approved single-repository v3 design; no hardware deployment. -->

# Active work

[Roadmap](docs/roadmap.md) owns scope. This file owns the execution order.
[Construction plan](docs/design/v3/README.md) owns detailed design within that
scope. Do not maintain parallel active queues in archived specifications.

## Current stage

**D0: single-repository v3 design and repository preparation.** The owner
approved this framework and README/construction-plan rewrite on 2026-11-10.
Hardware is not provisioned. The new responsibilities are documented; no
Terraform resources, Ansible plays, Helm chart, Flux manifests or deployment
workflow are implemented by this change.

Source baseline: a1bef2e on v3/development.
The [archive](docs/history/pre-v3/README.md) preserves original entry documents
and six older planning documents, with hashes and source commit.
The earlier pre-v3 tag preserves main at 2d8020a; it does not include later
preparation changes. Obsolete branch cleanup was independently verified.

## D0 deliverables in this change

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

- [ ] **D1.1 — resolve construction inputs.** Record versions, address/CIDR
  overlap checks, endpoint ownership, NAS protocol/export and backup/key/state
  recovery design. Output: reviewed architecture/storage/delivery amendments.
- [ ] **D1.2 — S3 compatibility slice.** In an isolated fixture environment,
  test the candidate implementation, image supply, PyIceberg/Trino/MLflow and
  current evidence/Object Lock semantics. Output: results, limits and an
  explicit selection/rollback decision; do not silently replace the reference.
- [ ] **D1.3 — implement one static infrastructure/bootstrap slice.**
  After inputs are decided, add actual definitions and applicable validation.
  Output: repeatable commands/results; no hardware deployment claim.
- [ ] **H0/H1 — accept hardware and construct the cluster.** Await machines
  and an explicit operational scope. Output: inventory, reproducible VM/K3s
  construction, API/quorum/failure and independent bootstrap recovery evidence.
- [ ] **H2 — GitOps test application.** Demonstrate reviewed release, drift
  correction and compatible rollback before deploying important state.
- [ ] **W0 — fixture finance migration and first consistent restore.**
  Preserve source/dataset semantics; validate Dagster Job, Iceberg/Gold/query,
  evidence and catalog+object recovery before important state admission.
- [ ] **W1/O0 — parity and operational acceptance.** Regress governance,
  metadata, MLflow and BI; measure load/SLOs, conduct isolated recovery drills
  and record observed RPO/RTO against selected objectives.

The detailed stage outputs and rollback boundaries are in
[migration and validation](docs/design/v3/migration-and-validation.md).

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
