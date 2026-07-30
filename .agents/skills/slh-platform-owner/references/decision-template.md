# Owner decision sources and evidence

Use the smallest set needed for the decision.

| Decision | Read first | Evidence to require |
|---|---|---|
| Priority, version scope, strategic fit | `docs/roadmap.md`, `TASKS.md` | Scope mapped to the active version and measurable outcome |
| v2.6 governance evidence | `docs/v2.6-demo-goal.md`, `docs/history/v2.6-planning.md` | Validated contract/lineage/evidence artifact; fail-fast behavior; limitations disclosed |
| Architecture change | `docs/architecture.md`, `docs/decisions/README.md` | ADR when non-trivial; baseline compatibility check |
| Runtime, deployment, release | `docs/release-readiness.md`, `docs/release.md`, `RUNBOOK.md` | Applicable readiness checks and captured command results |
| Dataset governance | `docs/dataset-governance-naming.md`, `docs/medallion-model.md` | Stable dataset identity, contract validation, and downstream compatibility |

Current strategic constraints:

- v2.5 is the protected Compose/Iceberg/Dagster/Trino/OpenMetadata/Superset baseline.
- v2.6 concentrates on executable governance and evidence, not Kubernetes, new engines, generic observability, or an agent UI.
- Do not claim compliance certification, immutable/WORM retention, or regulatory readiness without implementation and direct verification evidence.
