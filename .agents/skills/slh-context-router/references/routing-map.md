# SoloLakehouse routing map

| Task class | Canonical starting context | Route and validation |
|---|---|---|
| Priority, roadmap, major scope | `docs/roadmap.md`, `TASKS.md` | `$slh-platform-owner`; no code until approved |
| Code change or defect | Graphify query; target module; matching tests; `AGENTS.md` | Code agent; focused test/type/lint; run `graphify update .` after edits |
| Architecture | Graphify query or path; `docs/architecture.md`; `docs/decisions/README.md` | Architecture review; ADR assessment; preserve v2.5 baseline |
| Dataset governance / v2.6 | Graphify query; `docs/v2.6-demo-goal.md`; `docs/history/v2.6-planning.md`; `docs/dataset-governance-naming.md` | Governance implementation; validate contracts and fail-fast evidence paths |
| Operations / deployment / release | Graphify query; `RUNBOOK.md`; `docs/deployment.md`; `docs/release-readiness.md`; `docs/release.md` | Ops route; run named readiness or verification checks |
| Documentation | Graphify query; `docs/README.md`; target canonical document; source code only if claim depends on it | Docs route; verify links, current version state, and no unsupported claims |
| GitHub issue / PR / CI | Graphify query for local context; relevant GitHub skill and linked issue/PR context | GitHub route; inspect before changing code |

Always apply these constraints:

- When `graphify-out/graph.json` exists, query Graphify before broad repository browsing. Graphify finds context; canonical source files establish facts.
- v2.5 is the protected runtime baseline.
- v2.6 is governance/evidence work; it excludes Kubernetes, multi-engine expansion, generic observability, and agent UI work.
- `docs/DOCUMENTATION_COMPENDIUM.md` is generated convenience context, not the preferred source when the original document is available.
