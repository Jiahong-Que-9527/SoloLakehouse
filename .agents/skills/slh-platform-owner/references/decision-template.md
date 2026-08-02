# Owner decision sources and evidence

Use the smallest set needed for the decision.

| Decision | Read first | Evidence to require |
|---|---|---|
| Priority, version scope, strategic fit | `docs/roadmap.md`, `TASKS.md` | Scope mapped to the active version and a measurable outcome |
| Governance evidence | `docs/v2.6-demo-goal.md`, `docs/v2.6-release-readiness.md`, `governance/` | Validated contract/lineage artifact; fail-fast on every missing source; limitations disclosed |
| Architecture change | `docs/architecture.md`, `docs/decisions/README.md` | ADR when non-trivial; baseline compatibility check |
| Runtime, deployment, release | `RUNBOOK.md`, `docs/deployment.md`, `docs/v2.6-release-readiness.md` | Applicable readiness checks and captured command output |
| Dataset governance | `docs/dataset-governance-naming.md`, `docs/medallion-model.md` | Stable dataset identity, contract validation, downstream compatibility |

## Current strategic constraints

- **v2.5 is the protected runtime baseline** (Compose + Dagster + all-layer
  Iceberg + Trino + MLflow + OpenMetadata + Superset). It does not change before
  v3.0.
- **v2.6.0 is released**; **v2.6.1 is the active target** — operationalize the
  evidence plane rather than adding a new evidence category.
- **Decision gates** (`docs/roadmap.md`, "Open Decisions"; `AGENTS.md` §3).
  **D1 resolved (2026-08-02):** v2.8, then v2.7, then v2.9; independent external
  validation and operational rollout follow v2.9. **D2/D3** still block work
  behind the entity split or portal/Keycloak in compose — those require an Owner
  Decision (`needs-user-decision`).
- Each v2.x version delivers **one category of evidence**. Adding a new category
  while the previous one is manual, single-dataset, or overwritable is
  explicitly out of scope.
- Do not claim compliance certification, immutable/WORM retention, or regulatory
  readiness without implementation and direct verification evidence.
- Estimate with the **measured** velocity (v2.6 ran ≈2.9× its estimate). Approve
  version *order*, not dates.
