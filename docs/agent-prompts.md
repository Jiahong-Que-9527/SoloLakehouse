# Agent Prompt Reference

Prompts for AI coding agents working on this codebase.

## Baseline prompt

```
Read CLAUDE.md, docs/roadmap.md, and docs/history/timeline.md.
Confirm that the runtime baseline is v2.5 single-track (Dagster + OpenMetadata +
Superset are mandatory, and the runtime does not change before v3.0), and that
the current version is v2.6 (governance and evidence plane).
Then perform the task and report the files changed and how you verified them.
```

## Verification prompt

```
Run make verify, make demo, make pipeline, make test, make lint, and
make typecheck in that order.
Identify and fix any failures, then report the root cause and the fix.
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
