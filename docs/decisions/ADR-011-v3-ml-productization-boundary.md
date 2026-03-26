# ADR-011: v3 Defines ML Productization Boundary (Experiment Platform First)

**Status:** Accepted  
**Date:** 2026-03

## Context

v2 includes ML experiment orchestration and tracking, but full model serving lifecycle (registry-to-serving-to-monitoring) is not yet formalized. v3 must define scope boundaries to avoid overextension.

## Decision

v3 prioritizes **experiment platform productionization** over full online serving productization:

1. strengthen reproducible training/evaluation pipelines
2. enforce model artifact and experiment lineage governance
3. prepare integration points for serving systems, but defer full serving platform build to later phase unless explicitly required

## Rationale

**1) Scope control for platform maturity**  
Infrastructure and governance gaps are higher priority than immediate serving expansion.

**2) Better risk management**  
Shipping partial serving without mature observability/security/governance can create fragile production behavior.

**3) Higher leverage for current team size**  
Improved training and experiment reliability benefits all downstream ML use cases.

## Trade-offs

- no complete end-to-end online inference product in v3
- may require temporary external serving integration for advanced use cases

## Alternatives Considered

### A) Full serving platform in v3

- Pros: complete ML lifecycle narrative
- Cons: high complexity and risk of diluting core productionization goals
- Rejected for v3 scope

### B) No ML scope in v3

- Pros: simpler infrastructure focus
- Cons: weakens continuity of data-to-ML platform narrative
- Rejected

## Upgrade and Rollback Notes

### Upgrade

- standardize model metadata, artifact paths, and evaluation contracts
- define readiness criteria for introducing serving in later versions

### Rollback

- if ML scope expansion threatens v3 infrastructure objectives, freeze serving-related expansion and focus on experiment platform reliability goals

## Related Docs

- `docs/history/v3-planning.md`
- `docs/roadmap.md`
