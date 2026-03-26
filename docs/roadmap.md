# Roadmap

Development has reached **[v1.0](#v10)** as the first complete milestone: an **eight-layer** enterprise-style lakehouse (see [architecture.md](architecture.md)), plus a smooth first-run experience (health checks, docs, troubleshooting). **v2.0** broadens **self-serve** use and, in the implementation plan, adds **Dagster**-style orchestration — see the note at the end.

Earlier docs listed **v0.1–v0.7** as incremental releases; **this project does not ship those as separate versions**. Work is organised **toward v1.0** directly (see [EVOLVING_PLAN.md](EVOLVING_PLAN.md)).

---

## Versions

| Version | Status | Layers | Theme |
|---------|--------|--------|--------|
| **v1.0** | **Current** | 1–8 | Full platform: metadata, observability, user access; **effortless deployment** (prerequisites, health checks, CI, integration tests, troubleshooting — [EVOLVING_PLAN.md](EVOLVING_PLAN.md) Phase 2) |
| **v2.0** | Planned | — | Self-serve usability (docs-first onboarding, repeatable verification, clearer failure modes); optional UI/observability; Dagster DAG ([EVOLVING_PLAN.md](EVOLVING_PLAN.md) Phase 3) |
| **v3.0** | Planned | — | Production infrastructure: Kubernetes/Helm, Terraform, cloud provisioning ([CLAUDE.md](../CLAUDE.md)) |
| **v4.0** | Planned | — | Self-serve maturity (documentation, verification, failure clarity); overlaps in theme with v2.0 in some older tables — reconcile when versioning stabilises |

---

## v1.0

Combines:

1. **Architecture:** eight layers (multi-source ingestion, dedicated metadata, observability Prometheus/Grafana, user access e.g. CloudBeaver) — see the v1.0 diagram in [architecture.md](architecture.md) and [README.md](../README.md).
2. **Delivery:** one-command setup where possible, reliable health checks, lint/type/coverage in CI, integration tests, and troubleshooting guides.

---

## v2.0 and later

**v2.0** in product terms emphasises **self-serve** adoption. The **implementation plan** adds **Dagster** (assets, schedules, UI). Treat these as one major release with two facets: *usability* and *orchestration*.

**v3.0 / v4.0** extend infrastructure and self-serve maturity — see [CLAUDE.md](../CLAUDE.md).

---

## Note on naming

Older drafts used labels like “Effortless Deployment” vs “Full Enterprise Platform” for the same v1.0 goal. **This file and [architecture.md](architecture.md) are the canonical roadmap**; [EVOLVING_PLAN.md](EVOLVING_PLAN.md) is the detailed task backlog.
