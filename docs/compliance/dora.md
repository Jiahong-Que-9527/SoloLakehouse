# DORA Mapping

Source: Regulation (EU) 2022/2554 on digital operational resilience for the financial sector.

This mapping focuses on evidence surfaces in SoloLakehouse v2.5. It does not assert regulatory compliance.

| DORA area | Regulatory intent | SoloLakehouse v2.5 evidence | Related ADR / doc | Gap before production |
|---|---|---|---|---|
| Article 5, governance and organisation | Management owns ICT risk arrangements and data availability, authenticity, integrity, and confidentiality. | README and architecture docs define the stack, ownership boundary, and local-first runtime. | `docs/architecture.md`, ADR-001, ADR-006 | No formal governance workflow, RACI, or sign-off process. |
| Article 6, ICT risk management framework | ICT risk controls should be documented, reviewed, and integrated with risk management. | ADRs document architecture choices and consequences; `RUNBOOK.md` documents operational response paths. | ADR index, `RUNBOOK.md` | No annual review workflow or formal internal audit process. |
| Article 7, ICT systems, protocols, and tools | Systems should be reliable, proportionate, and capable of processing required data. | Docker Compose baseline with explicit resource requirements; `make verify` checks core services. | README prerequisites, `scripts/verify-setup.py` | No capacity testing or high-availability design in v2.5. |
| Article 8, identification | ICT-supported functions, assets, and dependencies should be identified and documented. | Architecture diagram, service table, dependency graph, and bind-mounted runtime state map. | `docs/architecture.md`, `docs/deployment.md` | No formal CMDB or asset inventory lifecycle. |
| Operational resilience testing | Controls should be tested and failures should be visible. | `make demo`, `scripts/verify-demo.py`, unit tests, integration test stubs, CI workflow. | Makefile, `.github/workflows/test.yml` | CI must prove full Compose demo before v2.5 freeze. |
| Incident response evidence | Failures should be diagnosable and recoverable. | Health dashboard and runbook provide service-level failure triage. | `scripts/health-server.py`, `RUNBOOK.md` | No incident ticket workflow or regulatory notification process. |

## v2.5 Boundary

v2.5 proves a local platform baseline can be started, checked, and demonstrated. DORA-grade production operation remains out of scope until the later productionization track adds environment promotion, SLOs, secrets governance, and Kubernetes deployment.
