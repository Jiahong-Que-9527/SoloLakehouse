# PVE resource contract

**Status: design only; hardware not provisioned.**

One planned 24GiB/8-vCPU K3s guest per 32GB/1TB physical host. Define names, interfaces, disks, placement, API identity, state backend/single-writer ownership and rebuild boundaries.

Do not commit actual variable files, plans/state, credentials or host keys. Static validation and actual provisioning need separate results. No .tf resource is delivered here.

See the [authoritative design](../../docs/design/v3/architecture.md) and [construction-plan index](../../docs/design/v3/README.md).
