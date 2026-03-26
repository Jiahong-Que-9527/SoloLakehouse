# ADR-008: v3 Environment Promotion Model is dev -> staging -> production

**Status:** Accepted  
**Date:** 2026-03

## Context

v2 release flow is coherent for single-path internal usage, but lacks explicit multi-environment promotion gates required for production posture.

## Decision

Adopt a strict promotion chain:

- `dev` -> `staging` -> `production`

Each promotion requires gated checks:

1. deployment success and health verification
2. pipeline execution success (default path + compatibility checks where required)
3. quality gates (tests/lint/typecheck + runtime data checks)
4. rollback readiness confirmation

## Rationale

**1) Reduces blast radius**  
Changes are validated in lower environments before production exposure.

**2) Establishes release governance discipline**  
Promotion criteria become explicit and repeatable.

**3) Improves incident response**  
Rollback points and known-good versions are easier to identify.

## Trade-offs

- slower release velocity for small fixes
- higher CI/CD pipeline complexity
- additional operational overhead for environment maintenance

## Alternatives Considered

### A) Single environment direct release

- Pros: fastest delivery
- Cons: highest risk and weakest reproducibility guarantees
- Rejected for v3 production goals

### B) Two-environment model (dev -> prod)

- Pros: less overhead than three-tier model
- Cons: insufficient pre-production validation layer
- Rejected

## Upgrade and Rollback Notes

### Upgrade

- define promotion checklist and artifacts per environment
- enforce release tagging and changelog linkage before production promotion

### Rollback

- rollback to last known-good tag in target environment
- temporarily freeze forward promotion until root cause and gate updates are completed

## Related Docs

- `docs/release.md`
- `docs/history/v3-planning.md`
