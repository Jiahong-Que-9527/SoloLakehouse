# Architecture Decision Records (ADRs)

This folder contains architecture decisions across versions.

## v1 decisions

- [ADR-001-docker-compose.md](ADR-001-docker-compose.md): Docker Compose over Kubernetes for v1
- [ADR-002-trino-vs-duckdb.md](ADR-002-trino-vs-duckdb.md): Trino + Hive Metastore over DuckDB-first
- [ADR-003-parquet-vs-delta.md](ADR-003-parquet-vs-delta.md): Parquet append-only over Delta Lake
- [ADR-004-financial-dataset.md](ADR-004-financial-dataset.md): ECB + DAX dataset selection
- [ADR-005-v1-scope.md](ADR-005-v1-scope.md): defer Prometheus/Grafana/CloudBeaver in v1

## v2 decisions

- [ADR-006-v2-dagster-orchestration.md](ADR-006-v2-dagster-orchestration.md): move default orchestration to Dagster with legacy fallback during migration

## How to add new ADRs

1. Create the next numbered `ADR-xxx-*.md` file.
2. Include: context, decision, rationale, trade-offs, alternatives, upgrade/rollback notes.
3. Cross-link the ADR in:
   - `docs/README.md`
   - `docs/history/architecture-evolution.md`
   - relevant version planning note in `docs/history/`
