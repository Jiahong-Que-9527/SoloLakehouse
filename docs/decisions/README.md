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

## v2.5 decisions (reference extension)

- [ADR-013-iceberg-gold-trino.md](ADR-013-iceberg-gold-trino.md): Apache Iceberg for Gold via Trino (`iceberg` catalog)
- [ADR-014-openmetadata-optional-profile.md](ADR-014-openmetadata-optional-profile.md): OpenMetadata as optional Docker Compose profile

## v3 decisions (planned)

- [ADR-007-v3-k8s-helm-terraform.md](ADR-007-v3-k8s-helm-terraform.md): adopt Kubernetes + Helm + Terraform as v3 production infrastructure baseline
- [ADR-008-v3-environment-promotion.md](ADR-008-v3-environment-promotion.md): enforce dev -> staging -> production promotion model with release gates
- [ADR-009-v3-secrets-and-access-governance.md](ADR-009-v3-secrets-and-access-governance.md): managed secrets and least-privilege access governance
- [ADR-010-v3-observability-and-slo.md](ADR-010-v3-observability-and-slo.md): SLO-driven observability and alerting baseline
- [ADR-011-v3-ml-productization-boundary.md](ADR-011-v3-ml-productization-boundary.md): define ML productization boundary (experiment platform first)
- [ADR-012-v3-data-governance-catalog-strategy.md](ADR-012-v3-data-governance-catalog-strategy.md): Hive-first governance baseline with upgrade-ready catalog strategy

## How to add new ADRs

1. Create the next numbered `ADR-xxx-*.md` file.
2. Include: context, decision, rationale, trade-offs, alternatives, upgrade/rollback notes.
3. Cross-link the ADR in:
   - `docs/README.md`
   - `docs/history/architecture-evolution.md`
   - relevant version planning note in `docs/history/`
