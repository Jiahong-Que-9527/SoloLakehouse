# ADR-006: v2 Orchestration Moves to Dagster (with Legacy Fallback)

**Status:** Accepted  
**Date:** 2026-03

**Amendment (v2.5 single-track, 2026-04):** Legacy script orchestration and Makefile fallbacks (`pipeline-v1`, `pipeline-legacy`, `PIPELINE_MODE`, `scripts/run-pipeline.py`) were **removed**. The body below describes the v2 migration design; rollback today is via an older release tag or restoring the removed files from history, not via `make` targets.

## Context

v1 orchestration relies on a linear script (`scripts/run-pipeline.py`). It is reliable for local execution, but has clear operational limitations:

- weak scheduling semantics
- limited lineage visibility
- coarse rerun granularity
- no framework-native sensor/check lifecycle

v2 requires an orchestrator that supports asset dependencies, retries, schedules, and operational UX while preserving local onboarding simplicity.

## Decision

Adopt Dagster as the default orchestration path in v2.

Key implementation choices:

1. Default run command switches to Dagster:
   - `make pipeline` executes `full_pipeline_job`
2. Legacy script remained available during early v2 migration (removed in v2.5+):
   - ~~`make pipeline-legacy` / `make pipeline-v1` / `make pipeline PIPELINE_MODE=v1`~~ invoked `scripts/run-pipeline.py` (file and targets no longer present)
3. Runtime services include:
   - `dagster-webserver`
   - `dagster-daemon`
4. Dagster run/event state uses PostgreSQL (`dagster_storage`) via `dagster/dagster.yaml`.

## Rationale

**1) Asset-native modeling fits the project's medallion flow.**  
Bronze/Silver/Gold/ML map naturally to Dagster assets and enable explicit lineage.

**2) Operational controls improve significantly.**  
Schedules, sensors, asset checks, and UI run history provide platform-level governance beyond script orchestration.

**3) Migration risk is controlled by dual-path execution.**  
Keeping legacy script execution avoids all-or-nothing cutover risk.

**4) PostgreSQL-backed Dagster state improves durability.**  
Run and event records persist across restarts and align with existing stateful-service model.

## Trade-offs

- Added runtime complexity (2 more services and Dagster dependencies)
- Temporary dual-path operations increase short-term cognitive load
- Postgres health becomes critical for orchestration state availability

## Alternatives Considered

### A) Keep script + cron wrappers

- Pros: minimal changes
- Cons: weak asset governance, poor lineage/check semantics
- Rejected: does not meet v2 operational goals

### B) Airflow/Prefect

- Pros: mature ecosystems
- Cons: migration overhead and lower alignment with current asset-centric plan
- Rejected for v2 scope and speed; may be revisited if constraints change

## Upgrade and Rollback Notes

### Upgrade

- Start Dagster services with Compose
- Run default pipeline through Dagster
- Use `docs/DAGSTER_GUIDE.md` for operations

### Rollback

- **Current stack:** there is no Makefile rollback to the legacy script; use a pre-removal git tag or branch if you must reproduce the old path.
- Preserve data path compatibility (no medallion storage format changes introduced by orchestrator switch)

## Related Docs

- `docs/history/architecture-evolution.md`
- `docs/history/timeline.md`
- `docs/history/v2-planning.md`
