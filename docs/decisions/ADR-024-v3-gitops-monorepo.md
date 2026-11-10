# ADR-024: Single-repository v3 construction design

**Status:** Accepted for repository/design scope; runtime choices remain conditional.  
**Date:** 2026-11-10

## Context

The owner chose to evolve the existing SoloLakehouse repository before the
planned three Mini PCs arrive. Earlier proposals described three repositories
and several unimplemented services. Existing code, reference deployment paths,
history and unfinished work must stay recoverable and accurately labelled.

## Decision

Keep one repository with application code, infra, bootstrap, reusable packaging,
GitOps and a single detailed construction plan. Preserve current Python/Compose
paths initially. Write responsibility documents now, not executable placeholders.

The target direction is PVE/OpenTofu, cloud-init/Ansible, K3s and Flux with
Helm/Kustomize and suitable SOPS/age encryption. Initial resources are one
24GiB server/worker VM per planned 32GB/1TB physical host. These are designs,
not measured capacity or deployed infrastructure.

Preserve signed historical originals in a hash-indexed pre-v3 archive, keep
compatibility pointers, and retain all unresolved work. Roadmap/TASKS remain
authoritative; detailed design is subordinate. Disable generic data-destruction
Make targets rather than introducing bypass flags.

## Open choices

Exact versions, network allocations, NAS protocol, S3 replacement/evidence
compatibility, recovery objectives and later storage/database HA still require
specific evidence and decisions. No host operation, live data migration,
extra repository, engine, portal, serving or autonomous agent is delivered.

## Relationship to older decisions

ADR-007's Kubernetes/Helm/IaC direction is refined for this monorepo design.
ADR-008/009/010/011/012/015 remain historical rationale; this decision does not
claim their runtime implementation. ADR-019 remains the historical v2.5 MinIO
freeze decision; object-storage selection is reopened only as a bounded
compatibility exercise. D2/D3/source/private-workload boundaries stay in force.

The older TASKS placeholders calling various future records “ADR-024” did not
reserve one identifier. This file is the actual 024; missing K11-K14/crypto
rationale is retained and receives an available number only when written.

## Alternatives

- Three repositories: clearer independent access boundaries, but not the
  owner's selected layout. Directory ownership preserves lifecycle separation.
- Large Python/Compose path migration now: unnecessary compatibility risk
  before the deployment contract is implemented.
- Empty executable skeletons: misleading validation and implied capabilities.

## Consequences and rollback

Public defaults, encrypted declarations and private bootstrap/state inputs need
clear ownership in the same repository. Preserve key/state recovery outside the
target cluster. Never describe ignored local inputs as Flux-reconciled content.

A current complete Git bundle was verified before edits; original texts and
hashes remain in the [archive](../history/pre-v3/README.md). Reverting design
commits restores configuration text, not business data. Runtime implementation
uses the staged [construction plan](../design/v3/README.md) and its own tests.
