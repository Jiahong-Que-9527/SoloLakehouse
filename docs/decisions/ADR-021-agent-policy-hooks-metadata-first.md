# ADR-021: Agent-Ready Policy Hooks (Metadata First)

**Status:** Accepted  
**Date:** 2026-08-02  
**Version:** v2.8 (E2/E3 design gate)

## Context

Dataset contracts already declare `approved_consumer_class` and
`access_policy_hint`, but nothing enforces them at query time. v2.8 needs
agent-ready policy hooks without expanding into a chat application platform or
changing the v2.5 service topology.

## Decision

For v2.8, **policy hooks are metadata and evidence-boundary validation only**:

1. Contract fields (`approved_consumer_class`, `access_policy_hint`, and future
   AI-governance extensions in E2) remain the declarative policy surface.
2. ML lineage binding (E1) includes `data_contract_hash`, so every MLflow run
   references the exact contract version in force at training time.
3. Evidence adapters continue to **fail loudly** when required governance fields
   are missing; they do not silently degrade.

**Deferred to v2.9 / v3:** runtime enforcement via Trino access-control
providers, secrets/access governance (Block D), or MCP proxy gates. Those require
platform changes beyond v2.8's evidence category.

## Consequences

- Agents and future MCP tools can read stable contract metadata and ML lineage tags today.
- The project does not claim production RBAC or regulatory enforcement in v2.8.
- E3 delivers structured policy-hook metadata; E4 consumes the five-tuple for model cards.

## Alternatives Considered

- **Trino access-control provider in v2.8** — rejected; violates v2.5 runtime freeze and v2.9 scope.
- **Contract fields only, no ML binding** — rejected; hooks would not attach to experiments.
- **Full agent/chat platform** — rejected; explicitly out of scope per roadmap.

## Related

- [ADR-018](ADR-018-ml-lineage-five-tuple.md)
- [ADR-009](ADR-009-v3-secrets-and-access-governance.md)
