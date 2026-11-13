# Delivery and environment design

**Design only.** No Flux objects, chart release, CI deployment credential or
cluster endpoint is installed by this change.

## Three control flows

| Flow | Owner | Expected change |
|---|---|---|
| Infrastructure | OpenTofu + cloud-init/Ansible | PVE VM/network inputs and K3s lifecycle |
| Application delivery | CI + reviewed configuration + Flux | Immutable package/image and desired deployment |
| Data/ML execution | Dagster + quality/evidence logic | Source partitions, tables, features and experiments |

Do not restart the cluster to retry a failed data partition. Do not rebuild
application images to resize a VM. Namespace and deployment ownership must be
unambiguous.

## Package and version contract

Existing Python modules remain in place. New packaging will define the actual
entrypoint, dependencies, image, service account, resources, probes and persistent
state for each component. Dagster currently uses DefaultRunLauncher; a future
K8sRunLauncher integration must include Job images, permissions, run concurrency,
termination/retry behavior and retained run/evidence identifiers.

| Artifact | Owner / contract |
|---|---|
| Application image | CI builds from a source commit, records digest and provenance |
| Reusable chart | One source under deploy/charts/slh; a versioned package references supported images/configuration |
| Environment values | gitops/apps/slh overlays select versions and environment differences |
| Cluster platform components | gitops/platform declares ownership, versions and dependencies |
| Runtime run/experiment | Dagster/MLflow preserve code/data/image identity where supported |

Do not duplicate the chart into GitOps. Do not use mutable `latest` as a release
identity. Chart/image promotion reuses the same tested artifact rather than
rebuilding a different image for each environment.

## Proposed application release flow

1. Submit a bounded source change.
2. CI runs applicable unit/type/contract checks, image build and planned supply
   checks. Infrastructure credentials are not required for an ordinary build.
3. Publish an immutable image and record the source commit and digest.
4. Submit a configuration PR changing the selected digest/chart and values.
5. Review the deployment diff, compatibility and state/rollback implications.
6. Flux pulls the reviewed desired state; Kubernetes performs the rollout.
7. Check readiness and a scoped functional data/API result, not only Pod status.
8. Retain the source commit, image digest, GitOps commit, run IDs and result.

CI does not routinely receive a cluster-admin kubeconfig or directly apply
application releases. Bootstrap and emergency work use separate scoped identities.
Flux requires sufficient permissions but should not grant every workload
cluster-wide control.

## Environment contract

| Environment | Purpose | State/source rules |
|---|---|---|
| Local Compose | Developer feedback and reference regression | Existing paths, explicitly selected local state |
| K3s dev/validation | Fixtures, static/render smoke checks and controlled migration tests | Separate namespace, service identities, database/schema/buckets |
| K3s staging | Release and restore rehearsal | Matching immutable artifacts, controlled inputs and capacity |
| K3s home/stable | Later continuously operated reference workload | Explicit live-source schedules, credentials, retention and SLOs |

These are logical environments within one planned cluster, not independently
available production clusters. Most non-primary environments run on demand;
do not keep three full metadata/Java stacks resident on 32GB hosts.

Use distinct names, database users, schemas, buckets/prefixes and network
policies. Never point a fixture or restore job at actual fin/avi state.
Only the designated stable environment runs the eventual live ingestion
schedule, with source calendars, quotas and freshness rules preserved.

## Configuration and secrets in a public monorepo

Current commits contain sanitized examples and design only. Future actual
configuration requires an explicit public/encrypted/local split:

- Public defaults: non-sensitive resource structure, supported settings and examples.
- Encrypted declarations: SOPS ciphertext where needed by Flux; review visible
  metadata as well as values.
- Independent private material: age private keys, kubeconfig, API credentials,
  IaC state, real provisioning variable/inventory files and recovery tokens.

Base64 is not encryption. Gitignored local inputs are not automatically reconciled
by Flux; documentation must state their independent owner and backup method.
Do not commit secrets in generated plans, rendered manifests, logs or screenshots.
Key rotation, runtime Secret protection and recovery are separate from Git
encryption.

Use one owner for each Kubernetes object. Keep bootstrap/CNI/API reachability
outside a dependency cycle with Flux. Apply dependency ordering for controllers,
CRDs, storage, secrets, databases and applications. Do not put persistent-data
resources under an unrestricted routine prune policy.

## D1.1 state and credential ownership

[Codex · 2026-11-13] Use a single-writer administration environment outside
the target cluster for the first VM. The platform operator owns the state
and recovery inventory. For the first VM, select the
[OpenTofu local backend](https://opentofu.org/docs/language/state/backends/)
on that administration environment and retain an encrypted independent
copy after every state-changing run. Serialize writes on that environment
and keep normal state locking enabled. Select a locking remote backend
before introducing concurrent automation. The exact administration host,
private backup destination and access procedure remain open and must be
verified before a live state-changing operation.

| Material | Classification and recovery input |
|---|---|
| Resource shape, version pins and sanitized examples | Public Git. Recover from the reviewed commit |
| PVE identity, real input inventory, OpenTofu state and plans | Private. Recover from the independent operator-controlled store using the backup and access record |
| Flux Git credential and bootstrap access | Private. Define read access for reconciliation and use a separate bootstrap identity if writes are needed. Verify credential reissue and Git reachability from outside the cluster before H2 |
| SOPS declarations and age keys | Suitable SOPS ciphertext may live in Git. Keep the age private key and any required recovery copy outside the cluster and Git. Confirm independent decryption of a test declaration before D1.4/H2 |
| K3s server token and snapshots | Private. Keep the matching token with a recoverable snapshot reference in the independent inventory and rehearse isolated restoration in H1. See [K3s backup and restore](https://docs.k3s.io/datastore/backup-restore) |

Recovery order: obtain administration access, Git and the private recovery
inventory outside the cluster. Recover infrastructure state and the
required PVE access. Recover K3s using the selected compatible version,
snapshot and token when restoring an existing cluster. Reestablish Flux
Git access and age decryption before reconciling applications. Verify actual
locations, access and recovery with a disposable test before relying on
them. D1.4 still needs the cluster endpoint, Git identity and recovery
inputs. H2 owns runtime reconciliation and rollback evidence.

## Promotion and rollback

Promote the same artifacts only after the defined checks for the destination
environment. A Git revert can restore application configuration when the old
version remains compatible with state. It cannot restore deleted objects,
revert database contents or safely reverse an arbitrary schema migration.

Record a backup/recovery point before stateful changes, migration compatibility,
allowed previous versions, stopping/resuming writers and rollback verification.
If the state boundary is irreversible, restoration or a forward fix is a
separate approved procedure. Keep deployment rollback and data recovery evidence
distinct.

## Validation before and after hardware

Now: document links, archive integrity, agent routing and Makefile safety.
When real definitions exist: OpenTofu validation, Ansible syntax, chart rendering,
schema/policy checks and a fixture integration plan.
On actual hardware: VM creation, K3s health, endpoint behavior, Flux change/drift/
rollback, persistent state and application/data acceptance.

A skipped or unavailable tool is not a passing check. Record the actual versions,
commands and limits of every validation layer.
