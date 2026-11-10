# V3 target architecture

**Design only — no new physical host or Kubernetes deployment is present.**

## Ownership within one repository

| Layer | Directory | Owns | Does not own |
|---|---|---|---|
| Physical preparation | infra/ | Host inventory, BIOS/installation notes, PVE/network prerequisites | Automatically discovering or reinstalling arbitrary hosts |
| VM lifecycle | infra/proxmox/ | Future OpenTofu resources, placement, disk/network inputs, IaC state design | Data pipelines or application releases |
| Guest/cluster bootstrap | bootstrap/ | cloud-init, Ansible, K3s initialization/upgrades/rebuilds | Flux-managed applications |
| Application packaging | deploy/charts/slh/ | Reusable SLH chart contract and defaults | Private environment values or VM lifecycle |
| Desired deployment state | gitops/ | Cluster entry point, platform dependencies, application versions/overlays | Scheduled ingestion or model training |
| Data/ML lifecycle | Existing Python modules and dagster/ | Contracts, transformations, quality, jobs, models and evidence | Provisioning hosts or reconciling Deployments |

An application chart has one owner in `deploy/`; GitOps references a version
instead of maintaining a second chart. The existing `docker/` and `config/`
paths remain in place for reference compatibility.

## Planned physical layout and resource budget

Three M6 Ultra hosts each have a procurement assumption of 32GB RAM, a 1TB SSD,
six physical CPU cores/twelve threads and two 2.5GbE interfaces.

| Per physical host | Initial planning budget |
|---|---|
| PVE and host cache | About 4GiB |
| One K3s server/worker VM | 8 vCPU; fixed 24GiB RAM |
| Unallocated physical headroom | About 4GiB |
| VM system disk | About 80GiB |
| VM data disk | Initially about 500GiB, subject to measured capacity/reserves |

vCPU allocations are scheduling limits, not additional physical cores. Keep
space for the host, images, snapshots, logs and storage headroom; do not allocate
the entire marketed SSD capacity. Two virtual disks on one SSD share its
failure and I/O domain.

With an illustrative 4GiB OS/control-plane reservation per VM, application
memory is about 60GiB with three nodes and 40GiB after losing one. Start critical
resident requests at no more than approximately 32GiB cluster-wide and limit
batch concurrency, then replace these estimates with measured CPU, RSS,
requests, throttling, disk latency and peak job use. Pause heavy training and
queries during degraded operation.

Do not assign one entire host exclusively to AI, another to data and another
to control at the start. Keep capacity usable across hosts and spread critical
replicas. A separate-worker VM layout is a later option, not a five-VM mandate.

## Failure domains

- Place one etcd member on each physical PVE host.
- Three etcd members retain quorum after one member fails; losing two loses
  quorum. Existing Pods continuing to run is not proof of a healthy control plane.
- Initial fixed placement avoids automatic PVE HA migration concentrating
  multiple members on one physical host. A later PVE HA design requires its
  own fencing, storage, capacity and placement validation.
- Application replicas need scheduling constraints and enough remaining capacity.
- Local PVCs do not move with a Pod. A database on the failed node may require
  node recovery or a restore even while the Kubernetes API remains available.
- One home, switch, power circuit and NAS remain shared dependencies.
  Namespaces do not create independent physical failure domains.

## Network design

Procure a managed 2.5GbE switch with at least eight appropriate ports and useful
expansion capacity. Three dual-NIC hosts, the NAS and an uplink already consume
eight connections. Optional 10GbE ports must match the intended NAS media/module;
a new switch alone does not upgrade the NAS NIC.

Use one host interface for management/Corosync and the other for VM/application
traffic where practical. VLANs separate logical traffic, not physical
bandwidth or switch failure. Keep Corosync and etcd on reliable low-latency
local wired paths; remote administration may use the existing trusted VPN.

Before assigning addresses, check LAN/VPN, guest, Pod, Service and load-balancer
ranges for overlap. Reserve stable host/VM names, DNS, NTP and an API endpoint.
The Kubernetes API VIP and application ingress address have separate roles.

The initial CNI direction is K3s Flannel. Traefik handles HTTP ingress.
If MetalLB is selected for application LoadBalancer services, disable the
competing K3s ServiceLB and keep any API-VIP mechanism scoped to the API.
Finalize versions, ownership and TLS behavior before writing bootstrap files.
Do not deploy two controllers to own the same endpoint.

## Bootstrap and external recovery dependencies

1. Prepare physical hosts, management access and networking.
2. Run reviewed OpenTofu changes from an administration environment outside
   the target K3s cluster.
3. Initialize guests, install K3s and verify etcd/API.
4. Supply independent bootstrap/decryption inputs and bootstrap Flux.
5. Reconcile platform dependencies, then applications.

IaC state, required K3s token, age private keys, image access and recovery
instructions must remain accessible when the cluster is absent. Start with a
controlled single-writer administration workflow and encrypted independent state
backup; select a locking remote backend before concurrent automation is added.
No IaC state is committed to Git.

## Workload and design boundaries

Finance remains the public reference. Aviation code and actual operated fin/avi
instances remain separate. This repository change does not authorize workload
migration or import private datasets. Retain existing source restrictions,
calendars, dataset identities and evidence contracts.

The reference Hive catalog, Dagster, Iceberg, Trino and MLflow semantics are
carried forward. Kubernetes packaging changes deployment ownership, not the
meaning of those data contracts. See [delivery](delivery-and-environments.md)
and [storage/recovery](storage-and-recovery.md).
