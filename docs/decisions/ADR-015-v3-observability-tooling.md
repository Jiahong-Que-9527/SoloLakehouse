# ADR-015: v3 Observability Tooling Uses Prometheus + Grafana

**Status:** Accepted  
**Date:** 2026-04

## Context

ADR-010 decided to adopt SLO-driven observability for v3 but deferred the specific tooling selection. ADR-005 explicitly deferred Prometheus/Grafana in v1 to avoid premature complexity before core orchestration was stable. v3 requires a concrete tooling decision to implement metrics collection, dashboards, and alerting rules for Tasks 63 and 69.

## Decision

Adopt **Prometheus + Grafana + Alertmanager** as the v3 observability stack:

1. **Prometheus** for metrics scraping and storage (pipeline success rate, Gold freshness, asset check pass rate, end-to-end latency)
2. **Grafana** for dashboards and alert rule definitions
3. **Alertmanager** (bundled with Prometheus) for alert routing and notification

Deploy as Kubernetes workloads alongside the core services. Not required in the local Compose dev path — structlog output remains sufficient for local development.

## Rationale

**1) Natural fit with Kubernetes**  
Prometheus is the de-facto standard for K8s metrics collection; service discovery works natively via Kubernetes SD configs.

**2) Open source and self-hosted**  
Consistent with the project's reference-implementation character; no vendor lock-in, API keys, or external billing required.

**3) Widely understood**  
Prometheus + Grafana is well-documented, has broad community tooling (exporters, pre-built dashboards), and is familiar to the target audience for this reference implementation.

**4) Dagster native integration**  
Dagster provides a `dagster-prometheus` integration for emitting pipeline-level metrics (run counts, step durations, asset materialisation success/failure) to a Prometheus pushgateway.

**5) Existing metric emission**  
Task 53 already emits timing metrics to structlog in a structured format; these can be redirected to a Prometheus exporter without restructuring the metric logic.

## Trade-offs

- operational overhead for maintaining Prometheus + Grafana alongside core services
- Prometheus is pull-based; metric endpoints must be exposed on each instrumented service
- initial dashboards require custom instrumentation for pipeline/data-product SLOs; generic infra dashboards alone are insufficient

## Alternatives Considered

### A) OpenTelemetry + backend-agnostic approach

- Pros: vendor-neutral, flexible collector pipeline
- Cons: higher setup complexity for a reference implementation; a backend still needs to be chosen
- Rejected for v3; may be reconsidered if multi-backend flexibility becomes necessary in v4+

### B) Managed observability (Datadog, New Relic, Grafana Cloud)

- Pros: zero infrastructure overhead, rich feature set
- Cons: vendor dependency, cost, reduced transparency as a reference implementation
- Rejected

### C) Logs-only (extend existing structlog)

- Pros: zero new infrastructure
- Cons: insufficient for SLO measurement and proactive alerting; rejected per ADR-010

## Implementation Scope

- Add `/metrics` endpoints (Prometheus exposition format) to Dagster webserver and daemon
- Use existing Trino JMX metrics exporter or trino-exporter sidecar
- Use postgres-exporter for PostgreSQL health and connection pool metrics
- Use minio-exporter for object storage capacity and request metrics
- Deploy Prometheus + Grafana + Alertmanager as a Helm dependency chart (e.g., `kube-prometheus-stack`)
- Define initial alert rules as code (PrometheusRule CRDs or Grafana provisioning files)
- Dashboard provisioning via Grafana configmaps; no manual dashboard creation required

## Related Docs

- ADR-005: Prometheus/Grafana deferred in v1 scope
- ADR-010: SLO-driven observability baseline decision
- `docs/EVOLVING_PLAN.md` Phase 4 (Tasks 63, 64, 69)
- `docs/history/v3-planning.md` M3
