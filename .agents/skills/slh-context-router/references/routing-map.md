# SoloLakehouse routing map

Authority reminder: `docs/roadmap.md` decides **what each version does**;
`TASKS.md` decides **what the next PR does**. Everything else defers to those
two. `AGENTS.md` carries the current state, decision gates, and hard rules.

| Task class | Canonical starting context | Route and validation |
|---|---|---|
| Priority, roadmap, major scope | `docs/roadmap.md`, `TASKS.md` | `$slh-platform-owner`; no code until approved |
| Code change or defect | Graphify query; target module; matching tests; `CLAUDE.md` patterns | Code agent; `make test lint typecheck`; run `graphify update .` after edits |
| Architecture | Graphify query or path; `docs/architecture.md`; `docs/decisions/README.md` | Architecture review; ADR assessment; preserve the v2.5 runtime baseline |
| Governance, contracts, lineage evidence | Graphify query; `governance/`; `docs/v2.6-demo-goal.md`; `docs/dataset-governance-naming.md`; `docs/v2.6-release-readiness.md` | Governance implementation; `make validate-contracts`; verify fail-fast on every missing source |
| Operations / deployment | Graphify query; `RUNBOOK.md`; `docs/deployment.md`; `docs/make-demo-guide.md` | Ops route; `make verify`, `make demo` |
| Release | `docs/v2.6-release-readiness.md`; `CHANGELOG.md`; `docs/history/timeline.md` | Release route; record the drill evidence and disclose limitations |
| Documentation | Graphify query; `docs/README.md`; the target canonical document | Docs route; verify links resolve **in the published repository**, and that no claim outruns the implementation |
| GitHub issue / PR / CI | Graphify query for local context; the linked issue/PR | GitHub route; inspect before changing code |

## Constraints that always apply

- When `graphify-out/graph.json` exists, query Graphify before broad repository
  browsing. Graphify finds context; canonical source files establish facts.
- **v2.5 is the protected runtime baseline** and does not change before v3.0.
- **Decision gates** — see `AGENTS.md` section 3. **D2:** entity split deferred.
  **D3:** portal/Keycloak is sandbox only. The next PR is in `TASKS.md`.
- The published repository is **English-only**; `docs/local-cn/` is local.

## Paths that are local-only

Some documents referenced in older material are not present in a fresh clone.
Do not route an agent to them and do not treat their absence as a defect:

- `docs/local-cn/**` — Chinese working documents
- `docs/history/v2.6-planning.md` … `v2.9-planning.md` — superseded 2026-05-05
  snapshots; use `docs/roadmap.md` instead
- `docs/release.md`, `docs/release-readiness.md`, `docs/V*_RELEASE_CHECKLIST.md`
  — internal runbooks; the published gate is `docs/v2.6-release-readiness.md`
- `docs/DOCUMENTATION_COMPENDIUM.md` — generated convenience context, never the
  preferred source when the original document is available
