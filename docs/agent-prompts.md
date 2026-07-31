# Agent Prompt Reference

Prompts for AI coding agents working on this codebase.

## Baseline prompt

```
Read AGENTS.md, then docs/roadmap.md and TASKS.md.
Confirm three things before starting:
  1. the runtime baseline is v2.5 single-track and does not change before v3.0
  2. the active target is v2.6.1 (operationalize the evidence plane)
  3. the task is not blocked by decision gate D1, D2, or D3
If a gate blocks it, stop and say so instead of proceeding.
Otherwise perform the task and report the files changed and how you verified them.
```

## Verification prompt

```
Run make verify, make demo, make pipeline, make test, make lint, and
make typecheck in that order.
Identify and fix any failures, then report the root cause and the fix.
```

## Decision-gate check

```
Check AGENTS.md section 3 and the "Open Decisions" section of docs/roadmap.md.
Report whether this task sits behind D1 (v2.7/v2.8 blocked), D2 (entity split
deferred), or D3 (portal/Keycloak sandbox only). If it does, do not implement —
return what would need to be decided first.
```

## Governance prompt

```
Run make validate-contracts.
For any governed dataset you touch, confirm that governance/datasets/<id>.yaml
still matches the physical table, the Dagster asset key, and the declared
quality rules. Never emit partial evidence: a missing source must fail loudly.
```

## Docs consistency prompt

```
Scan README.md and docs/.
Ensure no removed command or entrypoint is still referenced (for example
pipeline-v1, pipeline-legacy, PIPELINE_MODE).
Keep historical narrative under docs/history/.
Public documentation is English-only; do not add Chinese-language files to the
repository.
```

## Runtime troubleshooting prompt

```
Run make verify.
If it fails, work through the services in dependency order
(PostgreSQL, Hive Metastore, MinIO, Trino, MLflow, Dagster, OpenMetadata,
Superset), give actionable repair steps, and re-verify.
```
