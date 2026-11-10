<!-- [房玄龄·2026-11-10] Owner-approved single-repository v3 design; no hardware deployment. -->

# Reading order

1. Read [README](../README.md): actual reference code, v3 design and workload boundaries.
2. Read [roadmap](roadmap.md) and [TASKS](../TASKS.md): scope and the next output.
3. Read the [construction plan](design/v3/README.md) and only the detailed
   architecture/storage/delivery/migration sections needed for the task.
4. For code changes, read [AGENTS](../AGENTS.md), relevant
   [CLAUDE patterns](../CLAUDE.md), the affected modules and matching tests.
5. For existing local runtime work, use [quick start](quickstart.md) and
   [runbook](../RUNBOOK.md), with their image-supply and destructive-command limits.
6. For historical rationale, follow explicit links through the
   [archive index](history/pre-v3/README.md) or [ADRs](decisions/README.md).

<!-- [房玄龄·2026-11-10] Find next work without reviving historical queues. -->

For a fresh development session, use
[TASKS start/handoff](../TASKS.md#start-here-in-the-next-session) and the
[shared agent protocol](../AGENTS.md#starting-and-handing-off-work). Record
task ID, output, actual validation, gaps and next ID in the same PR. The
tool-specific files are pointers; they do not own additional work queues.

Hardware is not provisioned. Reading this guide does not require starting
containers, rebuilding a graph, installing cluster tools or executing all
historical examples. `make help`, `make docs-check` and
`make check-agent-docs` are the current non-runtime entrypoints.

Use [retained work](design/v3/retained-work.md) when reconciling older tasks.
The old entity split, external-validation campaign and crypto phase are not
reactivated by onboarding.
