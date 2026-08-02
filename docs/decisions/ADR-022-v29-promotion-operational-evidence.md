# ADR-022: v2.9 Promotion and Operational Evidence on the v2.5 Runtime

**Status:** Accepted  
**Date:** 2026-08-02  
**Version:** v2.9 (Blocks B and C)

## Context

ADR-008 and ADR-010 define the v3 promotion chain and SLO-driven observability
targets. v2.9 must produce **operational evidence** on the existing Docker
Compose runtime without adding Prometheus/Grafana or changing the protected v2.5
service set.

## Decision

1. Add machine-readable **promotion evidence** with a strict
   `dev -> staging -> production` transition chain (`governance/promotion.py`).
2. Add **rollback drill evidence** that resolves a configured
   `ROLLBACK_TARGET_TAG` and records the reference rollback command sequence.
3. Add **operational evidence** that evaluates platform SLOs from existing
   `make verify` health checks and binds in-repo incident runbook references
   (`governance/operations.py`).
4. Expose CLIs:
   - `make promotion-evidence`
   - `make rollback-drill`
   - `make operational-evidence`

Promotion and operational records fail loudly when required gates or SLOs fail,
matching the v2.6 evidence-plane rule.

## Consequences

- v2.9 demonstrates promotion/rollback discipline without claiming full v3
  environment automation.
- SLO evaluation reuses verify-setup checks; it does not introduce a new metrics
  stack before v3 (ADR-015).
- Full secrets/access rotation evidence remains in Block D (`v2.9 -> v3.0`).

## Related

- [ADR-008](ADR-008-v3-environment-promotion.md)
- [ADR-010](ADR-010-v3-observability-and-slo.md)
- [`docs/promotion-discipline.md`](../promotion-discipline.md)
- [`docs/operational-slo.md`](../operational-slo.md)
