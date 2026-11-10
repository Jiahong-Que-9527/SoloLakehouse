<!-- [房玄龄·2026-11-10] Owner-approved single-repository v3 design; no hardware deployment. -->

# Roadmap

This file decides **what the repository builds**. [TASKS](../TASKS.md) decides
execution order. The [v3 construction plan](design/v3/README.md) supplies detail
within those decisions; older specifications and history are reference only.

## Current position

As of 2026-11-10: the owner approved a **single-repository v3 design and
construction framework**. Three planned 32GB/1TB Mini PCs have not been
provisioned. New infra/bootstrap/deployment/GitOps directories contain design
documents, not a running cluster or executable deployment implementation.

The finance reference code and v2.5 Compose paths are retained. The clean-clone
MinIO client/image-supply issue and fresh runtime acceptance remain open.
Aviation is the main separately maintained operated domain; this public
repository does not acquire its private pipeline or data.

## Version and capability boundaries

| Area | Recorded state |
|---|---|
| v2.5 reference | Compose + Dagster + all-layer Iceberg + Trino + MLflow + OpenMetadata + Superset; preserve semantics |
| v2.6.1 tag | Released 2026-07-31; corrected version stamp; predates Block J |
| Blocks J/E/I/B/C/D/F | Implemented on main through v2.9; historical verification is not continuous live proof |
| Finance L4 phase 1 and L5-L7 | Landed on main via the recorded EWG/ECB/FX/freshness/Gold work |
| v3 | Design and repository preparation; hardware, IaC implementation, deployment and runtime acceptance not completed |
| Serving / operations agent | Later candidates; not a v3 infrastructure MVP requirement |

The [pre-v3 tag](https://github.com/Jiahong-Que-9527/SoloLakehouse/releases/tag/pre-v3-2026-11-10)
preserves main at 2d8020a. The detailed prior roadmap, release chronology,
original decisions and unfinished-task provenance are preserved in the
[pre-v3 archive](history/pre-v3/README.md) and [timeline](history/timeline.md).

## V3 scope

Build a platform one person can deploy, understand, observe and recover:

1. A reproducible PVE/VM/K3s construction path, with manual physical prerequisites stated.
2. One repository with infra, bootstrap, reusable packaging, GitOps and application ownership.
3. Reviewed immutable delivery, logical environment separation, secrets and access boundaries.
4. Existing finance/Iceberg/governance/MLflow/metadata/BI capability migration.
5. Tested consistent state recovery and measured operational behavior.

Keep Compose as a reference path. Preserve application semantics while migrating
the deployment boundary. Do not couple new services, data sources, object-store
replacement, catalog replacement and Python-package reorganization in one change.

## Decisions that remain in force

| Decision | Current boundary |
|---|---|
| D1 | The approved v2.8 → v2.7 → v2.9 evidence sequence is historical and delivered; independent external sign-off was cancelled as a blocking gate on 2026-08-15. Internal evidence remains required. |
| D2 | Product/entity split is deferred indefinitely. The old [task.md](../task.md) is historical design, not an active implementation track. Directory separation inside this repository does not reopen it. |
| D3 | Portal/Keycloak exploration remains sandbox-only; no addition to reference Compose, env templates or version scope is authorized. |
| D4 | Static DAX sample CSV is retired. The approved reference market leg is live EWG via Alpha Vantage, with committed JSON fixtures for controlled tests. Crypto phase 2 stays deferred. |
| D5 | Finance L5-L7 are delivered; calendars, FX interpretation, freshness and source limits remain. FRED/electricity/new symbols are not new authorized work. |
| D6 | Personally operated platform; aviation primary operated domain, finance public reference; separate aviation implementation and honest source/proxy/evidence boundaries. Unfinished aviation evidence/reliability work is retained. |
| D7 | Prepare v3 in the existing repository. Baseline tag/full Git archive and obsolete-branch cleanup were verified. The 2026-11-10 owner amendment authorizes the monorepo framework, complete construction plan, entry-document rewrite, byte-preserved historical archive and safe command changes. It does not authorize host/service deployment or workload/data migration. |

## Selected target and unresolved implementation choices

Selected design: three PVE hosts, one K3s server/worker VM per host, OpenTofu
for declared virtual resources, cloud-init/Ansible for bootstrap, Flux with
Helm/Kustomize for applications and SOPS/age for suitable encrypted declarations.
See [ADR-024](decisions/ADR-024-v3-gitops-monorepo.md).

Initial storage design favors local PVCs with independent NAS backup; it does
not claim stateful HA. Retain Hive Metastore for the first slice. A maintained
S3 implementation, image supply, evidence/Object Lock compatibility, backup
protocol, network allocations, exact versions and RPO/RTO/SLO targets still need
evidence-based decisions. No Ceph or Longhorn installation is included now.

## Order and acceptance

<!-- [房玄龄·2026-11-10] Owner-requested actionable roadmap and next-session route. -->

D0 repository preparation is merged (#100), with the diagram (#101) and cover
(#102). **Next: D1.1 construction inputs**, still pending. Before hardware,
resolve network/switch requirements, compatible versions, capacity, NAS backup
access, private/public configuration and independent key/state/bootstrap recovery.
The output is a recorded decision set and a bounded first-VM implementation contract.

Then implement small, independently verifiable slices: isolated fixture S3
compatibility (D1.2), one static VM/cloud-init definition (D1.3), and minimal
Flux configuration for a stateless test app (D1.4). D1.2 and D1.3 can proceed
independently once their respective inputs are ready; S3 acceptance is required
before W0 data migration, not before declaring a VM. Runtime validation of the
GitOps configuration happens in H2 after a real cluster exists.

Use [TASKS](../TASKS.md#next-bounded-work) for the single actionable queue,
dependencies, deliverables and acceptance; use its
[D1.1 inputs](../TASKS.md#d11-inputs-and-acceptance) for the next session.
Listing future work does not authorize target-host operations or migration.
No D1 implementation is claimed by this roadmap update.

Follow [construction stages](design/v3/migration-and-validation.md):
repository design → bounded static implementation → hardware acceptance →
reproducible cluster → GitOps test workload → fixture reference data →
capability parity → operational/recovery acceptance.

Deliver version order and evidence, not a promised eight-week timeline.
Distinguish design, static validation and actual runtime validation. No production
SLA, regulatory certification, immutability or HA claim is inferred from diagrams,
installed tools or historical runs.

## Retained and deferred work

[TASKS](../TASKS.md) owns the active queue.
[Retained-work provenance](design/v3/retained-work.md) maps all previously
unchecked items, stale checkboxes, deferred crypto and unfinished D6 work.
Earlier completion marks and original wording remain in the source snapshot.

No automatic import of aviation code, existing fin/avi migration, extra engine,
cloud platform, serving product or autonomous production agent is in scope.
Old ADRs retain their identities; [history](history/README.md) explains prior
choices without making those documents competing current instructions.
