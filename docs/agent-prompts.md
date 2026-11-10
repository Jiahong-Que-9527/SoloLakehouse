<!-- [房玄龄·2026-11-10] Owner-approved single-repository v3 design; no hardware deployment. -->

# Agent task reference

Read [AGENTS](../AGENTS.md), [roadmap](roadmap.md) and [TASKS](../TASKS.md).
Prompts route to current authority rather than hard-coding a stale work block.

## Design task

```text
Read the current roadmap, TASKS and relevant v3 design section.
State the requested output, actual authorization, preserved reference behavior,
and what remains design-only. Make only that bounded change.
Do not provision hosts, deploy services or migrate data during repository design.
Report actual checks and any unexecuted validation.
```

## Code task

```text
Read AGENTS, the affected code and matching tests.
Check source/dataset and private-workload boundaries.
Use available Graphify context if the project graph exists; verify owning sources.
Keep compatibility changes separate from unrelated directory reorganization.
Run appropriate checks and report observed behavior, not assumed success.
```

## Historical cleanup task

```text
Find callers and links before classifying a file as unused.
Preserve signed originals and source provenance before substantial rewrites.
Carry every unfinished item forward or document its evidence-based classification.
Exact-target approval is required before destructive file/data/volume disposal.
Do not run clean/reset/purge commands to inspect their behavior.
```

## Verification task

```text
Choose checks proportional to the change.
For active docs/scaffold use docs-check and check-agent-docs.
For runtime/code changes add applicable lint, type, contract, unit/integration
and explicit runtime acceptance. Do not silently turn a read-only check into
installation, remote changes or data cleanup. Distinguish skipped from passed.
```
