# ADR-012: v3 Data Governance Catalog Strategy (Hive-First, Upgrade-Ready)

**Status:** Accepted  
**Date:** 2026-03

## Context

v2 uses Hive Metastore as the catalog backbone with Trino query access and medallion data layout in object storage.  
For productionization (v3), governance requirements increase:

- finer-grained access policies
- stronger lineage/discovery expectations
- multi-environment consistency
- future compatibility with table formats/catalog upgrades

The project needs a catalog strategy that is realistic for current scope while remaining upgrade-ready.

## Decision

v3 keeps a **Hive-first catalog strategy** as the default governance baseline, and defines an explicit **upgrade path** toward richer catalog/governance systems when scale and compliance requirements justify it.

Concretely:

1. Keep Hive Metastore as the primary catalog in v3 baseline
2. Standardize naming conventions, schema ownership, and environment separation rules
3. Add governance metadata conventions (dataset owner, quality class, refresh SLA) in docs and table contracts
4. Define migration checkpoints for future catalog uplift (e.g., Iceberg catalog strategy / enterprise unified catalog layer)

## Rationale

**1) Scope realism for v3**  
v3 already introduces major infra shifts (K8s/Helm/Terraform, security, observability). Replacing catalog stack simultaneously raises delivery risk.

**2) Preserves architectural continuity**  
Current Trino + Hive + object storage model remains stable and operationally understandable.

**3) Upgrade-friendly posture**  
By adding governance conventions now, future migration becomes structured rather than ad-hoc.

**4) Better interview and stakeholder clarity**  
This avoids “tool-chasing” and shows controlled maturity planning: baseline now, enterprise lift when justified.

## Trade-offs

- Governance depth is improved but not equivalent to full enterprise unified catalog products
- Some metadata governance remains convention-driven in v3
- Future migration effort is intentionally deferred, not eliminated

## Alternatives Considered

### A) Immediate move to advanced unified catalog stack in v3

- Pros: stronger governance feature set sooner
- Cons: high migration complexity during already heavy infra transition
- Rejected for v3 timeline risk

### B) Stay fully as-is with no governance standardization

- Pros: fastest short-term delivery
- Cons: governance debt accumulates quickly; weak enterprise readiness signal
- Rejected

## Upgrade and Rollback Notes

### Upgrade

- define governance metadata contract and ownership map
- enforce naming/schema conventions across environments
- capture migration criteria (dataset scale, policy complexity, audit needs) for next catalog step

### Rollback

- if governance rollout causes instability, keep existing Hive runtime while rolling back only governance enforcement layers (not storage/query primitives)

## Related Docs

- `docs/history/v3-planning.md`
- `docs/roadmap.md`
- `docs/decisions/ADR-007-v3-k8s-helm-terraform.md`
- `docs/decisions/ADR-009-v3-secrets-and-access-governance.md`
