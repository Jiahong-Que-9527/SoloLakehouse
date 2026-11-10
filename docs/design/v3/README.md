<!-- [房玄龄·2026-11-10] Owner-approved single-repository v3 design and construction plan; hardware not provisioned. -->

# V3 construction plan

**Stage: design and repository preparation.** Hardware is not provisioned.
This is the single detailed construction plan for the existing SoloLakehouse
repository. [Roadmap](../../roadmap.md) owns scope and [TASKS](../../../TASKS.md)
owns the active queue. Earlier three-repository proposals are not the chosen
layout.

## Decisions and evidence status

| Subject | Current decision / boundary | Evidence maturity |
|---|---|---|
| Repository | Keep one SoloLakehouse repository; separate infra, bootstrap, packaging, GitOps and application responsibilities by directory | Owner-approved design |
| Hosts | Three planned M6 Ultra systems, 32GB/1TB each | Procurement assumption; not provisioned |
| Cluster | One K3s server VM per physical PVE host; server also schedules workloads | Design; not deployed |
| Storage | Local SSD/PVC first, independent NAS backup; no initial Ceph or Longhorn deployment | Design; restore untested |
| Object store | Preserve the S3 contract; evaluate a maintained implementation before migration | Candidate decision; compatibility untested |
| Catalog | Retain Hive Metastore initially | Design to limit migration variables |
| Delivery | OpenTofu, cloud-init/Ansible, Flux, Helm/Kustomize, immutable images, SOPS/age | Toolchain design; no executable configuration yet |
| Environments | Local Compose plus logical validation/stable K3s environments | Design; no separate physical isolation |
| Existing workloads | Finance reference retained; aviation implementation and operated fin/avi environments remain separate | Existing boundary |
| ML | Training, evaluation, tracking and evidence; serving/operations agent deferred | Scope boundary |

Use **design only**, **statically checked**, and **runtime verified** precisely.
A document may be checked while the system it describes remains unimplemented.
Attach the command/result/date to a validation claim; never promote an entire
component because one unrelated check passed.

## Read the plan

1. [Architecture](architecture.md): repository ownership, resource model,
   physical failure domains, network and bootstrap dependencies.
2. [Storage and recovery](storage-and-recovery.md): persistence, S3 selection,
   backup consistency, restore sequence and recovery decisions.
3. [Delivery and environments](delivery-and-environments.md): CI/GitOps
   contracts, identities, configuration, promotion and rollback.
4. [Migration and validation](migration-and-validation.md): all construction
   stages, entry/exit evidence, rollback and retained work.

[ADR-024](../../decisions/ADR-024-v3-gitops-monorepo.md) records the accepted
repository/design boundary. It does not approve unresolved storage choices or
claim a running cluster.

## Construction sequence

| Stage | Work | Required output |
|---|---|---|
| D0 — merged framework | Repository layout, authoritative planning, archive, safe commands and documentation checks | Coherent reviewed design with preserved history |
| D1 — before hardware | Resolve open decisions; implement only a bounded static configuration slice when authorized | Reproducible render/validation records for actual files |
| H0 — hardware | Accept hardware, install and configure PVE, establish reliable networking | Inventory and tested host/network baseline |
| H1 — cluster | Provision three VMs, install K3s, establish API endpoint and recovery inputs | Rebuild and single-host-failure evidence |
| H2 — GitOps | Bootstrap Flux and deploy a small test application | Change, drift and rollback demonstration |
| W0 — data | Validate S3, migrate the fixture finance path and Dagster Jobs | Iceberg/Gold/query and consistent-restore evidence |
| W1 — parity | Regress governance, metadata, MLflow and BI; introduce controlled live reference inputs | Capability-by-capability migration record |
| O0 — acceptance | Measure load, alerts, failures and recovery; close applicable retained work | Bounded v3 acceptance report |

Hardware arrival is not a reason to skip storage or credential recovery design.
Complete the first isolated state restore before admitting important state.
Stage names establish ordering, not an eight-week completion commitment.

<!-- [房玄龄·2026-11-10] Single next-action source and bounded pre-hardware slices. -->

The immediate next output is [D1.1 construction inputs](../../../TASKS.md#d11-inputs-and-acceptance).
The [active queue](../../../TASKS.md#next-bounded-work) defines pending IDs,
dependencies and acceptance for S3 compatibility, one VM/cloud-init slice and
minimal GitOps configuration. These are planned artifacts, not implemented
definitions; runtime checks still depend on the corresponding isolated or
hardware environment. Do not maintain another checklist in this plan.

## Decisions that must remain open

- Exact switch, VLAN/CIDR and endpoint allocations, following overlap checks.
- PVE/K3s/guest OS/provider/chart versions and upgrade compatibility.
- Actual NIC/SSD behavior, power-loss restart and thermal/resource limits.
- NAS backup protocol/export, throughput, retention and independent offsite copy.
- S3 implementation, build/image supply, Object Lock/evidence compatibility.
- Database HA or block replication, if measured availability requirements justify it.
- Concrete RPO/RTO and SLO targets after a representative baseline.
- Which actual configuration may be public, encrypted in Git, or local-only.

Record the choice, alternatives, affected services, validation and rollback in
the relevant design/ADR when evidence is available. Do not encode guessed
addresses, credentials or unreviewed products in an executable placeholder.

## What the current scaffold contains

The four new areas contain responsibility documents, not Terraform resources,
Ansible plays, Helm charts, Flux CRs or a deployment workflow. A directory
named `infra` is not infrastructure as code until it contains implemented and
tested definitions. No cloud account, extra repository, host, service, or new
data source is created by D0.

## Completion record

Repository checks belong in the PR/validation result. Runtime and recovery
results belong in the later stage record and must state the tested workload,
data, versions, host conditions and limits. The active work is in
[TASKS](../../../TASKS.md); the [archive](../../history/pre-v3/README.md)
preserves prior decisions and all retained-task provenance.
