# BaFin BAIT Mapping

Sources: BaFin Circular 10/2017 (BA), "Bankaufsichtliche Anforderungen an die IT", and BaFin's English information page for BAIT.

This mapping treats BAIT as a supervisory IT-control lens for German banking environments. It does not assert that SoloLakehouse is compliant.

| BAIT area | Supervisory intent | SoloLakehouse v2.5 evidence | Related ADR / doc | Gap before production |
|---|---|---|---|---|
| IT strategy | IT architecture should support business and risk objectives. | README explains why the stack exists: local-first, self-hosted, audit-ready lakehouse engineering. | README, `docs/roadmap.md` | No institution-specific IT strategy approval. |
| IT governance | Roles, responsibilities, and control ownership should be clear. | ADRs assign rationale to technical decisions; version acceptance criteria define freeze ownership. | ADR index, `docs/v2.5-acceptance-criteria.md` | No formal role matrix or control owner register. |
| Information risk management | Information assets and risks should be identified and controlled. | Architecture docs list services, dependencies, ports, and persistence locations. | `docs/architecture.md`, `docs/deployment.md` | No risk register or risk acceptance workflow. |
| Information security management | Controls should protect availability, integrity, confidentiality, and authenticity. | Local secrets are isolated to `.env`; MinIO/PostgreSQL/Trino access is self-hosted for demo use. | `.env.example`, ADR-009 | Real secrets management deferred to v3. |
| User access management | Access should be controlled and reviewable. | v2.5 documents default demo credentials and local-only scope. | `docs/deployment.md`, README | No RBAC hardening or periodic access review in v2.5. |
| IT operations | Operations should be monitored, recoverable, and documented. | `make verify`, health dashboard, and `RUNBOOK.md` provide repeatable operational checks. | Makefile, `RUNBOOK.md` | No 24/7 monitoring, alerting, or on-call rotation. |
| IT projects and application development | Changes should be traceable and tested. | CI runs lint, typecheck, and tests; ADRs document non-trivial decisions. | `.github/workflows/test.yml`, ADR index | Full Compose demo CI still needs to be green before freeze. |
| Outsourcing / third-party services | External service dependencies should be understood. | v2.5 is self-hosted locally and avoids managed SaaS lakehouse dependency. | ADR-001, ADR-002, ADR-003 | External live data provider availability still needs explicit fallback documentation. |

## v2.5 Boundary

BAIT-style production maturity requires formal governance, access review, change management, incident management, and continuity processes. SoloLakehouse v2.5 is a reference implementation that makes the technical evidence surfaces visible before those enterprise controls are layered on.
