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

## D1.1 network and VM decision record

[Codex · 2026-11-13] First-pass evidence from the Windows IPv4 route table
(`route print -4`) and WSL Ubuntu IPv4 routes/addresses (`ip -j -4 route
show table main`, `ip -j -4 addr show scope global`). The source routes
are private. This view covers the workstation and its visible routes.

| Observed or planned network | K3s default Pod and Service CIDR comparison | Remaining validation |
|---|---|---|
| Workstation LAN, Hyper-V subnet and visible WSL container bridge networks, including down bridges | Neither default intersects the observed prefixes | Repeat on the target PVE host, router and recovery workstation |
| Tailscale interface and visible peer host routes | Neither default intersects the observed routes | Compare all approved/advertised subnet routes and reconnect any relevant VPN before the final comparison |
| Target PVE management and VM networks, NAS route and ingress address pool | Open | Obtain the actual private allocation and compare all routed prefixes pairwise. Verify that individual endpoint addresses are reserved on the intended subnet and outside DHCP/dynamic pools |

The [K3s defaults](https://docs.k3s.io/cli/server) are `10.42.0.0/16` for
Pods and `10.43.0.0/16` for Services. Keep them as candidates until the
target comparison is complete. Record the final result privately with
the sources, date and any conflict resolution. Use distinct DNS identities
for the PVE node, VM, API endpoint and app ingress. Bootstrap owns the API
endpoint and its TLS SANs. Traefik owns HTTP ingress. Leave the VIP and
LoadBalancer implementation open until the router/VLAN and ownership checks
are complete. If MetalLB is selected, the design already requires ServiceLB
to be disabled.

Switch requirement: managed 2.5GbE with 802.1Q VLAN support and at least
eight usable ports for six host links, one NAS link and one uplink. An
eight-port layout uses every port at that count. Verify the actual uplink,
spare ports and compatible media before selecting a model. The recorded
NAS link was 1 Gbps. Confirm whether the router can route and filter the
planned VLANs and whether the chosen uplink can carry them. Until then,
switch model, bridge mapping, VLAN IDs and address allocations are open.

### First-VM compatibility and sizing

Sources checked 2026-11-13. Select these as the **initial validation
candidates**. Exact host build, guest image checksum and installed tool
versions must be recorded before first use.

| Component | Candidate or design decision | Remaining evidence |
|---|---|---|
| Host | [PVE 9.2](https://www.proxmox.com/en/about/company-details/press-releases/proxmox-virtual-environment-9-2) release line | Confirm the installed build, kernel, NIC/storage behavior and update path in H0 |
| Guest | [Debian 13 amd64](https://www.debian.org/releases/trixie/amd64/) cloud image with cloud-init and QEMU Guest Agent | Pin a Debian cloud image build and checksum. Verify cloud-init data source, agent support and boot in the first authorized runtime slice |
| VM definition | [OpenTofu 1.13.9](https://github.com/opentofu/opentofu/releases/tag/v1.13.9) and [bpg/proxmox 0.122.0](https://github.com/bpg/terraform-provider-proxmox/releases/tag/v0.122.0) as a candidate pair. [Provider documentation](https://github.com/bpg/terraform-provider-proxmox) targets PVE 9.x | Confirm the pinned provider schema for VM disks, NIC, cloud-init and agent in D1.3. Verify required API privileges and TLS against the selected PVE build before use |
| K3s | Use a supported stable release with an exact version recorded before H1, following the [K3s requirements](https://docs.k3s.io/installation/requirements) and [upgrade order](https://docs.k3s.io/upgrades/manual) | Select the exact release with the actual guest kernel and chosen add-ons. Bootstrap the first server and validate DNS/CNI before extending to the remaining hosts |

Record the previous validated image and tool/provider pins before a change.
For the disposable first guest, validate a rebuild with the prior guest image
and configuration. For a later stateful K3s upgrade, confirm the supported
version path, back up etcd with its matching token and use the documented
rollback and restore procedure. Stop after the first node if the health checks
fail.

Carry forward the draft budget of 8 vCPU, fixed 24 GiB RAM, about 80 GiB
system disk and initially about 500 GiB data disk. Before provisioning, compare
actual usable RAM and disk capacity in GiB with the host reserve, both VM disks,
and space for images, logs and snapshots. Keep the data disk separately
identified and leave its filesystem and workload placement for the
appropriate implementation slice. H0 measures available capacity and link
behavior. H1 measures VM usage and cluster headroom.

### D1.3 single-guest input contract

| Input | Sanitized specification |
|---|---|
| Placement | One x86-64 PVE node. Use placeholders `PVE_NODE`, `VM_ID`, `VM_STORAGE` and `SNIPPET_STORAGE` |
| Guest | Example name `slh-test-01`, verified Debian 13 cloud image and checksum, cloud-init user-data, QEMU Guest Agent |
| Resources | 8 vCPU, 24 GiB fixed RAM, 80 GiB system and 500 GiB data disk as initial example values |
| Network | `VM_BRIDGE`, optional `VM_VLAN_ID`, reserved guest address or documented DHCP reservation, DNS and gateway. The static example uses placeholders |
| Access | Dedicated least-privilege PVE identity, trusted CA, operator public SSH key supplied as input, unique VM ID and admin access from outside the target cluster |

Before a live run, an operator checks the host build, storage capabilities
and space, cloud-image provenance, VM ID availability, network allocation,
API privileges and trust chain. D1.3 scopes the static definition to
`infra/proxmox/` and `bootstrap/cloud-init/`. See the
[TASKS acceptance commands](../../../TASKS.md#d13-static-acceptance-commands).

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
