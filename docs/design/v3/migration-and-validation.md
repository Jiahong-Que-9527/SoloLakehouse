# Construction, migration and validation

This is the complete implementation sequence after repository design. Stage
completion requires its own evidence. Hardware has not been provisioned; runtime
stages below are not complete. The active next action is in
[TASKS](../../../TASKS.md), not a second checklist maintained here.

## D0 — repository preparation (this change)

Deliver one authoritative design, four responsibility areas, a clear README,
preserved historical originals, retained unfinished work, and safe command
entrypoints. Do not change Python import paths, data identities, Compose paths,
service versions or existing data.

Verify active links/anchors, byte-preserved archive hashes, agent entrypoints,
Makefile safety and applicable code/static checks. Record unavailable checks
honestly. A full Compose test is separate and must not be inferred from CI's
Python checks.

## D1 — decisions and static implementation, before hardware

Implement one bounded configuration slice at a time, after its design is chosen.
Required inputs are version selections, overlap-checked network ranges,
placement/resource limits, backup destinations/credentials, and component owners.

Expected artifacts, when implemented:

- OpenTofu modules and sanitized environment examples with state/lock ownership;
- cloud-init/Ansible inputs, idempotent bootstrap, explicit upgrade/rebuild paths;
- actual Helm chart defaults, probes, images, services, identities and persistence;
- Flux entrypoint, dependency order and environment overlays;
- scoped validation and change-review workflows.

Only then run the corresponding format/validate, Ansible syntax, Helm lint/render
and manifest/schema checks. These can prove a static configuration contract
without new hardware, not host provisioning or data availability. Do not create
placeholder manifests simply to make a check pass.

Keep real tfvars, inventory, plans/state, private keys and kubeconfig outside
public commits. Preserve encrypted recovery copies. No auto-apply or scheduled
deployment is part of D0.

Use [TASKS](../../../TASKS.md#next-bounded-work) for D1.1 inputs, D1.2 S3
compatibility, D1.3 first VM/cloud-init and D1.4 minimal GitOps configuration.
D1.2 and D1.3 can proceed independently after their respective inputs; S3
compatibility blocks W0 state migration rather than the VM definition. D1.4
static render/schema checks do not satisfy H2 reconciliation/drift/rollback.

## H0 — physical acceptance and PVE

1. Accept the first machine's actual RAM/SSD/NIC configuration and BIOS options.
2. Test memory, wired links, sustained thermal/CPU/I/O behavior and power-return
   behavior in a dedicated non-destructive acceptance scope.
3. Record host inventory, versions and firmware; do not publish actual private
   addresses, serials or access material.
4. Install and standardize PVE; establish time, DNS, administration access,
   low-latency wired networking and explicit local storage allocation.
5. Form the three-host cluster and confirm quorum and management reachability.
6. Verify backup destination access and independent recovery instructions.

Exit evidence: actual configuration and measured host/link behavior, usable
management paths, storage reserves, quorum, and documented manual preparation.
Rollback: preserve host/data boundaries; reinstall or reconfigure only an
explicitly scoped test/new host. Do not use a generic reset procedure.

## H1 — provision and recover the cluster

Create three declared guests, one per host. Configure fixed RAM, appropriate
virtual disks/interfaces and guest integration. Establish the stable API endpoint,
server token handling and three embedded-etcd members before admitting SLH state.

Exit evidence:

- a guest can be reproduced from its approved definition;
- all intended nodes and etcd members are healthy;
- API access and the chosen endpoint survive one controlled host outage;
- workload capacity and affected local volumes are recorded during degradation;
- member replacement and an isolated etcd snapshot/token restore are rehearsed.

Do not clone or restore an old etcd identity into a simultaneously live member.
VM snapshots and automatic PVE migration are not a substitute for the validated
membership/recovery procedure. Failure drills need an isolated scope and a
known restoration path.

## H2 — establish GitOps with a small application

Bootstrap Flux from the external administration environment. Restore/supply its
Git access and decryption inputs independently. Reconcile controllers/CRDs,
secret handling, networking and a small stateless test workload in dependency order.

Demonstrate:

1. reviewed configuration changes produce the expected rollout;
2. a controlled configuration drift is reconciled;
3. an application version/configuration can be rolled back;
4. cluster absence does not make the only state/key/bootstrap copy inaccessible.

Keep API ingress and application ingress ownership explicit. If MetalLB replaces
ServiceLB, configure that choice consistently on all K3s servers. Observe TLS,
readiness and routing rather than merely counting Ready nodes.

## W0 — migrate one reference data flow

Validate the chosen S3 implementation in isolation first; keep Hive Metastore
for the first slice. Reuse the existing fixture inputs and business semantics.

| Order | Component / contract | Acceptance |
|---|---|---|
| 1 | Persistent S3 and service databases | Credentials, endpoint, persistence and an isolated restore work |
| 2 | Hive Metastore and Iceberg namespaces | Catalog resolves intended objects and tables |
| 3 | Trino | Query expected schema and controlled fixture results |
| 4 | Dagster webserver/daemon/code image | Intended assets and schedules visible; no unintended live schedule |
| 5 | Kubernetes run launcher | A bounded Job runs the reference pipeline with intended identity/resources |
| 6 | Bronze/Silver/Gold and quality | Partition/write semantics, counts, quality failures and snapshot identity checked |
| 7 | Evidence | Code/image/run/dataset/snapshot identifiers and digests retain their meaning |

Preserve source calendars, time zones, overwrites/idempotency and existing
deprecated dataset identities. A new deployment target is not permission to
rename logical datasets, replay a final consumed test set or merge separate
finance/aviation data.

First restore: recover catalog/database and required object versions into an
isolated environment, deploy matching configuration, then verify Gold, quality
and lineage. Do this before important or continuously written state is admitted.

Rollback: retain the Compose reference and previous compatible images. Keep
test/new-state locations separate. Do not point the old and new writers at the
same tables until a deliberate cutover design is approved.

## W1 — capability parity and controlled operation

Regress existing capabilities individually:

- finance ECB/EWG/FX collectors, transformation outputs and freshness calendars;
- contract validation, quality rejection and typed lineage/evidence;
- OpenMetadata ingestion, ownership/lineage and stated evidence limitations;
- MLflow tracking, reproducible training/evaluation, artifact retrieval and model
  evidence, without claiming a serving deployment;
- BI query/dashboard behavior and operational evidence adapters;
- run concurrency, restart/retry behavior, storage reserve and credentials.

Functional regression evidence may use controlled test input; label that fact.
A historical run, synthetic drill or running UI is not current end-to-end proof.

Next enable only the intended stable reference ingestion schedule. Verify quota,
calendar and freshness behavior over a representative observation window.
Dev/staging run on demand with distinct identities/data boundaries. Existing
fin/avi instances stay untouched; aviation adaptation is separately scoped.

## O0 — operational acceptance

Establish lightweight metrics/alerts before adding a large logging stack.
Observe host/guest resources, disk reserve and latency, node/etcd health,
rollouts/restarts, job success, source-aware freshness and quality/evidence failures.

Define each SLI with numerator, denominator, exclusions, observation window and
source calendar. Choose SLOs after measuring a baseline; do not copy a 99% target
without considering the number of scheduled daily runs. Distinguish targets
from observed results and avoid an externally guaranteed SLA claim.

Exercise isolated deployment rollback, host loss, failed upstream validation,
database restore and consistent lakehouse recovery. Record:

- versions, source/GitOps commits, image digests and tested data volume;
- expected versus observed service behavior and affected capabilities;
- backup age, objective and measured RPO/RTO;
- failures, corrective actions, limits and the repeatable verification command.

## Cutover and rollback record

Before any later workload cutover, decide source/destination state, write freeze
or synchronization boundary, catalog/object consistency point, source quotas,
schedule ownership, supported application/schema versions and exact rollback
criteria. Confirm who approves stateful migration and how the original instance
remains recoverable.

A failed validation stops that stage; it does not justify deleting original
state or silently weakening a contract. Persist evidence of partial progress.
Full migration remains incomplete until required reference capabilities and
recovery have passed their scoped checks.

## Retained work and later extensions

The [retained-work ledger](retained-work.md) preserves every unchecked item
from the previous TASKS snapshot, plus unfinished D6 work. Re-evaluate scope
without marking old work complete merely because its number is old.
In particular, keep concurrency, capacity/freshness, secrets checks, backup/
restore and schema/JDBC/lifecycle work visible.

Crypto, new domains, Spark/REST catalog replacement, online serving, a portal
and an operations agent are not automatic consequences of v3. A later extension
needs a bounded decision, compatibility plan and evidence.

## Definition of a completed v3 migration

- Declared guest/cluster construction is reproducible with independent recovery inputs.
- Reviewed immutable releases, drift handling and compatible rollback are demonstrated.
- Reference data and existing governance/ML/metadata/BI capabilities pass scoped regression.
- Important state can be restored consistently, with measured loss/time limits.
- Resource/operational behavior is measured under normal and one-host-degraded conditions.
- Source and proxy-label boundaries, separate operated environments and unresolved
  limitations remain explicit.

No fixed delivery date or whole-platform HA claim follows from this plan.
