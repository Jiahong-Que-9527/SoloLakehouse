# ADR-010: v3 Observability Baseline Uses SLO-Driven Metrics and Alerting

**Status:** Accepted  
**Date:** 2026-03

## Context

v2 provides structured logs and basic runtime signals but lacks production-grade alerting and SLO-backed operations required for on-call reliability.

## Decision

Adopt an SLO-driven observability baseline in v3:

1. define service and pipeline SLOs
2. instrument metrics for critical paths (orchestration success, freshness, latency, data quality checks)
3. establish alerting rules tied to SLO violations
4. maintain incident runbooks linked to alert classes

## Rationale

**1) Move from reactive debugging to proactive operations**  
SLO-driven alerts reduce mean time to detect and improve operational confidence.

**2) Better production readiness**  
Reliability becomes measurable and reviewable.

**3) Supports team operations scaling**  
Shared dashboards and runbooks reduce tribal knowledge risk.

## Trade-offs

- instrumentation and dashboard overhead
- risk of noisy alerts if thresholds are immature
- requires ownership for observability maintenance

## Alternatives Considered

### A) Logs-only operations

- Pros: lowest implementation effort
- Cons: poor early detection and weak reliability contracts
- Rejected

### B) Generic infra metrics only

- Pros: quick bootstrap
- Cons: misses pipeline/data-product-specific failure modes
- Rejected as sole strategy

## Upgrade and Rollback Notes

### Upgrade

- start with minimal SLO set and expand iteratively
- validate alert quality in staging before production rollout

### Rollback

- if alert storms occur, switch to reduced alert profile while thresholds are recalibrated

## Related Docs

- `docs/history/v3-planning.md`
- `docs/EVOLVING_PLAN.md` (Phase 4 observability tasks)
