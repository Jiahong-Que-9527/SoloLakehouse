# ADR-023: v2.9 Secrets Discipline and K8s Readiness Evidence

**Status:** Accepted  
**Date:** 2026-08-02  
**Version:** v2.9 (Blocks D and F)

## Context

ADR-009 and ADR-007 define v3 managed secrets and Kubernetes infrastructure.
v2.9 must produce operational evidence on the existing Compose runtime without
adding Vault, External Secrets, Helm charts, or Terraform modules yet.

## Decision

1. Split local configuration templates into `.env.shared.example` and
   `.env.secrets.example`, with `make init-env` merging them into `.env`.
2. Add machine-readable secrets discipline evidence
   (`governance/secrets_discipline.py`, `make secrets-discipline`) and a manual
   rotation drill recorder (`make secrets-rotation-drill`).
3. Add a Kubernetes migration readiness gate
   (`governance/k8s_readiness.py`, `make k8s-readiness`) that verifies v2.9
   evidence prerequisites and marks v3-only infra items as deferred.

## Consequences

- Local onboarding can adopt the split env discipline without changing CI, which
  still uses `.env` / `.env.example`.
- Managed secrets and Helm/Terraform remain explicitly out of scope until v3.0.

## Related

- [ADR-009](ADR-009-v3-secrets-and-access-governance.md)
- [ADR-007](ADR-007-v3-k8s-helm-terraform.md)
- [`docs/secrets-discipline.md`](../secrets-discipline.md)
- [`docs/k8s-readiness.md`](../k8s-readiness.md)
