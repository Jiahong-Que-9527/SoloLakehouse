# Roadmap

Development has delivered **v1.0** and is now in **v2.0 (current)**: an orchestration-first platform upgrade with Dagster while preserving local reliability and migration fallback.

Earlier docs listed **v0.1–v0.7** as incremental releases; **this project does not ship those as separate versions**. Work is organised **toward v1.0** directly (see [EVOLVING_PLAN.md](EVOLVING_PLAN.md)).

---

## Versions

| Version | Status | Layers | Theme |
|---------|--------|--------|--------|
| **v1.0** | Delivered | 1–8 | Full platform baseline: metadata, observability target, user access path, and effortless deployment flow |
| **v2.0** | **Current** | + Orchestration | Dagster asset orchestration, schedule/sensor/check governance, default pipeline migration with legacy fallback ([EVOLVING_PLAN.md](EVOLVING_PLAN.md) Phase 3) |
| **v3.0** | Planned | — | Production infrastructure + governance: Kubernetes/Helm, Terraform, environment promotion controls, secrets/access governance, SLO/alerting ([CLAUDE.md](../CLAUDE.md)) |
| **v4.0** | Planned | — | Self-serve maturity (documentation, verification, failure clarity); overlaps in theme with v2.0 in some older tables — reconcile when versioning stabilises |

---

## v1.0 (delivered)

Combines:

1. **Architecture:** eight layers (multi-source ingestion, dedicated metadata, observability Prometheus/Grafana, user access e.g. CloudBeaver) — see the v1.0 diagram in [architecture.md](architecture.md) and [README.md](../README.md).
2. **Delivery:** one-command setup where possible, reliable health checks, lint/type/coverage in CI, integration tests, and troubleshooting guides.

---

## v1 -> v2 transition

v2 keeps the v1 data/ML modules and upgrades orchestration semantics:

- default path: `make pipeline` (Dagster job)
- migration fallback: `make pipeline-legacy` (script)
- added runtime services: `dagster-webserver`, `dagster-daemon`
- added governance: schedule, sensor, asset check, run/event persistence

See [v1-to-v2-transition.md](v1-to-v2-transition.md) for a complete migration narrative.

---

## v2.0 and later

**v2.0** in product terms emphasises **self-serve + orchestration**. The current implementation uses Dagster assets, schedules, sensor/check governance, and UI-driven operations.

**Deployment suitability (current v2):**

- Suitable: small internal teams, MVP-grade internal data platform, low-to-moderate scale batch workflows
- Not yet recommended: enterprise production platform requiring multi-environment HA, strict security/compliance, full observability and on-call-grade operations

### v3.0 planning focus (productionization)

v3 moves from “operable MVP platform” to “production-capable platform” with four pillars:

1. **Infrastructure**: Kubernetes + Helm + Terraform for reproducible multi-environment deployment
2. **Security/Governance**: secrets lifecycle, finer-grained access control, auditability
3. **Reliability/Observability**: metrics, alerting, SLOs, incident runbooks
4. **Operations Model**: environment promotion, rollback standards, and release gates

**v3.0 / v4.0** extend infrastructure and self-serve maturity — see [CLAUDE.md](../CLAUDE.md).

---

## Note on naming

Older drafts used labels like “Effortless Deployment” vs “Full Enterprise Platform” for the same v1.0 goal. **This file and [architecture.md](architecture.md) are the canonical roadmap**; [EVOLVING_PLAN.md](EVOLVING_PLAN.md) is the detailed task backlog.
