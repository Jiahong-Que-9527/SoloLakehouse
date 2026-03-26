# Architecture Evolution and Planning Choices

This document explains not only what architecture exists, but why certain options were chosen at each stage.

## 1) v1 foundation choices (implemented)

### Choice A: Docker Compose first, Kubernetes later
- **Selected:** Docker Compose
- **Alternatives considered:** Kubernetes from day one
- **Why selected:** lower setup friction, faster local iteration, easier for reference implementation onboarding
- **Trade-off accepted:** limited production parity and scaling semantics in early versions
- **Reference:** `docs/decisions/ADR-001-docker-compose.md`

### Choice B: Trino over embedded query engines
- **Selected:** Trino + Hive Metastore
- **Alternatives considered:** DuckDB-first architecture
- **Why selected:** demonstrates federated SQL and metadata-driven lakehouse patterns
- **Trade-off accepted:** more service complexity than embedded query engines
- **Reference:** `docs/decisions/ADR-002-trino-vs-duckdb.md`

### Choice C: Parquet without Delta transaction layer
- **Selected:** Parquet + append-only medallion conventions
- **Alternatives considered:** Delta Lake ACID table format
- **Why selected:** lower operational complexity for reference and education goals
- **Trade-off accepted:** no native ACID/time-travel layer in v1
- **Reference:** `docs/decisions/ADR-003-parquet-vs-delta.md`

## 2) v2 architecture decision frame (to fill during planning)

### Orchestration model
- **Candidate options:** Dagster, Prefect, Airflow, script-plus-cron
- **Primary criteria:** dependency modeling, retry semantics, local UX, operational overhead
- **Current direction:** Dagster (see `docs/EVOLVING_PLAN.md` Phase 3)

### Runtime scope
- **Candidate options:** keep script as fallback vs full orchestrator migration
- **Primary criteria:** migration risk, onboarding speed, troubleshooting complexity

## 3) v3 architecture decision frame (to fill during planning)

### Infrastructure target
- **Candidate options:** Kubernetes + Helm + Terraform, managed cloud stack, hybrid approach
- **Primary criteria:** reproducibility, operational burden, cost, team skill profile

### State and metadata portability
- **Candidate options:** managed services vs self-hosted parity
- **Primary criteria:** lock-in risk, disaster recovery, migration complexity

## 4) Planning method for future versions

For each major version, document decisions with this structure:

1. **Problem statement:** what scaling/usability gap vN must close
2. **Options matrix:** at least 2-3 viable paths
3. **Selection criteria:** performance, complexity, cost, onboarding, failure modes
4. **Decision and rationale:** why this path now
5. **Rollback strategy:** how to recover if choice underperforms
6. **Revisit trigger:** explicit condition that reopens this decision later
