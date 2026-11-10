# Storage and recovery design

**Design only.** No disk, NAS export, bucket, PVC or backup job is configured
by the repository scaffold.

## Persistence map

| State | Initial direction | Required recovery evidence |
|---|---|---|
| PVE/guest definition | Versioned definitions plus documented physical preparation | Rebuild an isolated guest without depending on the target K8s |
| Kubernetes state | Embedded etcd on local SSD | Snapshot + matching K3s server token restore |
| PostgreSQL service databases | Explicit persistent local volumes initially | Consistent database backup/restore, identities and version compatibility |
| Hive catalog | Preserve current implementation; persist its backing database/configuration | Catalog pointers resolve after data recovery |
| S3 objects | Maintained S3-compatible implementation, still to be selected | Iceberg objects/metadata and model/evidence artifacts recover consistently |
| MLflow | Database plus artifact objects and fixed model identity | A restored run resolves the expected artifact and code/data lineage |
| Secrets/bootstrap | Encrypted backups outside target cluster | A recovery operator can re-establish access without storing keys in Git |
| Telemetry | Bounded retention and capacity | Useful failure/recovery history without exhausting data disks |

PVE local LVM-thin and guest ext4 are the proposed simple starting layout.
Local PVCs preserve explicit node affinity and recovery responsibility. Separate
VM disks manage capacity; they do not add a second physical SSD.

## NAS boundary

The existing NAS was observed on 2026-11-10 as a DS923+ with approximately 32GB
RAM, a Btrfs volume with roughly 8.4TiB available, and an active 1Gbps link.
Only array membership was checked; no disk-health, throughput or restore test
was performed. NFS export configuration was not readable with the authorized
non-password access, so it is not confirmed or enabled.

Use dedicated, explicitly approved backup destinations; do not mount an
existing general-purpose share as an experimental data directory. Select the
protocol, permissions, retention and quotas before configuring jobs.
VM archives and application backups are different backup products.

At 1Gbps, theoretical wire throughput is about 125MB/s before overhead.
Measure backup and restore windows; do not derive RTO from free capacity.
A NAS serving backups is independent of the three compute hosts but still
shares its own chassis, disks and local site. Multiple copies on that NAS do
not establish offsite protection. Plan an additional independent copy for
important recovery material.

## Object storage decision

Current Compose references MinIO and an unpinned client image. The MinIO
community repository is archived and describes source-only distribution:
[upstream](https://github.com/minio/minio). The historical
[ADR-019](../../decisions/ADR-019-minio-seaweedfs-deferral.md) preserved MinIO
for the v2.5 freeze; it did not choose it permanently.

Keep the S3 interface. SeaweedFS is the first proposed compatibility candidate,
not an approved replacement or an implemented cluster:
[upstream](https://github.com/seaweedfs/seaweedfs).
Before selecting any replacement, record:

- maintained image/build source, pinned version/digest and reproducible build;
- authentication, least-privilege bucket access and TLS/endpoint behavior;
- PyIceberg and Trino writes/reads, multipart, range reads and retries;
- MLflow artifact upload/download and fixed model identity;
- listing, deletion, versioning and garbage-collection behavior;
- current audit/evidence and Object Lock APIs, retention semantics and limits;
- backup, restore, upgrade and interoperability results.

Passing ordinary S3 reads does not prove Object Lock or existing evidence
semantics. An unsupported capability needs an explicit design/claim change,
not a silent fallback. Perform the first compatibility exercise in isolation
before coupling it to the K3s migration. Retain Hive Metastore initially to
avoid replacing the object store and catalog in the same change.

## Replication decision

Initial scope excludes a Ceph or Longhorn deployment. First establish measured
workload use, recoverability and the desired application availability.

Later choose the primary replication mechanism per stateful service:
database-native replication/operator for database availability, or a justified
block-storage layer. Do not multiply replica counts across Ceph, Longhorn and
the application without calculating capacity and recovery pressure.

With three 500GiB data allocations, two block copies yield at most 750GiB
logical capacity before reserves and snapshots. That arithmetic does not
establish throughput, resilience or fit for this workload. Longhorn's
[performance guidance](https://longhorn.io/docs/1.13.0/best-practices/)
recommends 10Gbps; the planned 2.5GbE environment needs its own tests.

## Consistent lakehouse recovery

A catalog restored to one time and object data restored to another can point
to missing metadata/data files. Coordinate the recovery point:

1. Record the source commit, image versions, dataset IDs, current catalog
   pointer, Iceberg metadata/snapshot identity and relevant run/experiment IDs.
2. Establish a controlled write boundary or another documented consistency
   mechanism; capture database/catalog and required object versions.
3. Record exactly which state belongs to that recovery point and retain the
   required credentials/configuration separately.
4. Restore into a fresh isolated namespace/environment, not over the only copy.
5. Restore service databases/configuration and object versions in the
   implementation-specific tested order; then resolve catalog pointers.
6. Deploy the matching application configuration and verify Iceberg metadata,
   SQL access, expected counts/schema/quality, artifact availability and lineage.
7. Resume writes only after compatibility and consistency checks succeed.

Do not use Git revert as a database downgrade. Coordinate schema migrations,
supported version windows and state recovery independently of deployment rollback.

## Recovery objectives and drills

Targets remain to be selected; no measured RPO/RTO is claimed. The record must
separate objective from observed result and include backup age, data loss window,
elapsed restore time, data volume, throughput and failed steps.

| Drill | Required observation |
|---|---|
| Single host unavailable | etcd/API behavior, remaining capacity, affected local state |
| Guest loss/replacement | Controlled member replacement; no duplicate live etcd identity |
| etcd restore | Snapshot and matching token available; isolated recovery procedure works |
| Database restore | Expected schema/data/users and dependent services work |
| Catalog + S3 restore | Consistent snapshot/pointers, Gold query and quality validation |
| Model/evidence restore | Artifact identifiers and digests resolve to the expected run |
| Lost controller/configuration | Independent bootstrap and decryption material reconstruct delivery |

First restore validation precedes important state admission. Rehearse later
cross-layer failures under an explicit, isolated drill scope. PVC/PV, namespace,
VM disk and bucket retention must survive routine application reconciliation.
The legacy generic data-destruction Make targets are disabled; a future disposal
procedure must name exact targets, impact, backup and approval.
