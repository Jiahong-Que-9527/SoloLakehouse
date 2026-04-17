# ADR-007: v3 Uses Kubernetes + Helm + Terraform for Production Infrastructure

**Status:** Accepted  
**Date:** 2026-03

## Context

v2 is suitable for small-team internal MVP usage but not yet for production-grade operations. Core gaps include:

- limited environment parity (single-node Compose primary path)
- limited HA/scaling controls
- weak infra-as-code governance for repeatable deployments

v3 requires a production-oriented infrastructure foundation.

## Decision

Adopt:

1. **Kubernetes** as runtime control plane
2. **Helm** as application packaging/deployment abstraction
3. **Terraform** as infrastructure provisioning baseline

Keep Docker Compose for local development and demo portability.

## Rationale

**1) Environment reproducibility and promotion discipline**  
K8s + Helm + Terraform provides clearer dev/staging/prod parity than ad-hoc host scripts.

**2) Operational controls and scaling**  
Kubernetes unlocks probes, rollout policies, resource quotas, and autoscaling patterns.

**3) Team-scale governance**  
Terraform-managed infra reduces configuration drift and supports auditable infra changes.

**4) Compatibility with current architecture**  
Current service-oriented decomposition (MinIO/Postgres/Trino/MLflow/Dagster) maps naturally to K8s workloads.

## Trade-offs

- higher platform complexity and operational learning cost
- increased CI/CD and secrets management requirements
- slower initial iteration if over-scoped

## Alternatives Considered

### A) Keep Compose and harden scripts

- Pros: minimal complexity increase
- Cons: weak production parity, limited HA controls
- Rejected for v3 production goals

### B) Move directly to managed vendor platform

- Pros: reduced infra ownership
- Cons: significant architecture shift, lower transparency for reference implementation goals
- Rejected for now

## Upgrade and Rollback Notes

### Upgrade

- phase in K8s by environment (dev -> staging -> prod-like)
- keep compose local path until K8s flow is stable

### Rollback

- if K8s release path regresses, continue release-critical demos and local validation via Compose path

## Related Docs

- `docs/history/v3-planning.md`
- `TASKS.md` (Blocks F-G)
