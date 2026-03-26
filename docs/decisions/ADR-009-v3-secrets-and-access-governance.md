# ADR-009: v3 Introduces Managed Secrets and Least-Privilege Access Governance

**Status:** Accepted  
**Date:** 2026-03

## Context

v2 relies on environment-variable-centric local defaults, which is acceptable for internal MVP workflows but insufficient for production governance, compliance, and security audit expectations.

## Decision

For v3:

1. move runtime secrets to managed secret sources (instead of static `.env` assumptions)
2. enforce least-privilege service credentials
3. establish auditability for credential use and access changes

## Rationale

**1) Security posture uplift**  
Hardcoded/local default credential patterns are not acceptable in production environments.

**2) Compliance readiness**  
Managed secrets and auditable access changes align better with regulated fintech expectations.

**3) Operational safety**  
Credential rotation and revocation become tractable without invasive code changes.

## Trade-offs

- additional platform dependencies and setup complexity
- credential management workflows require team onboarding
- secrets outages become a first-class operational dependency

## Alternatives Considered

### A) Keep `.env` model with stricter process

- Pros: low complexity
- Cons: weak auditability and rotation guarantees
- Rejected

### B) Embed secrets in CI variables only

- Pros: easier than full secret provider integration
- Cons: incomplete runtime governance and weaker operational controls
- Rejected

## Upgrade and Rollback Notes

### Upgrade

- phase by service (database, storage, orchestration, ML endpoints)
- document fallback behavior for non-production local runs

### Rollback

- in incident scenarios, temporarily revert to restricted emergency credentials while maintaining audit trail and immediate rotation plans

## Related Docs

- `docs/history/v3-planning.md`
- `docs/deployment.md`
