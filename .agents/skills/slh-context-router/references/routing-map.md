<!-- [房玄龄·2026-11-10] Owner-approved monorepo design and safe repository entrypoints. -->

# Routing map

Roadmap defines scope; TASKS defines the next output. Current authorization and AGENTS override historical defaults.

| Task | Minimal source | Validation |
|---|---|---|
| Next development task / handoff | TASKS.md next-session output and acceptance, docs/roadmap.md scope, AGENTS.md shared protocol | record task ID, actual checks/evidence, gaps and next ID in the same PR |
| Repository design | docs/design/v3/README.md and one detailed design section | docs-check, check-agent-docs |
| Runtime/code | affected module, CLAUDE patterns and matching tests | applicable lint/type/contract/unit checks; explicitly scoped runtime evidence |
| Infrastructure/bootstrap | infra/ or bootstrap/ README, architecture and recovery design | actual static definitions first; provisioning only in an authorized target scope |
| Deployment/GitOps | deploy/ or gitops/ README, delivery/environment design | actual chart/manifest checks when implemented; no pretend pass for absent templates |
| Cleanup/history | callers/links, pre-v3 manifest and retained-work ledger | preserve originals and open-task coverage; exact approval for destructive targets |
| Old decisions | ADR index and explicit source snapshot | treat as historical, not a competing active queue |

When a Graphify graph exists, query it before broad code discovery and verify owning sources. If absent, use this route without installing/rebuilding a graph merely to orient. D2/D3/source/private-workload boundaries remain; current decision wording is in roadmap/AGENTS. Local-only notes are not missing public features.
