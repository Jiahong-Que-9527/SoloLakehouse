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

## 2) v2 orchestration choices (implemented)

### Orchestration model
- **Candidate options:** Dagster, Prefect, Airflow, script-plus-cron
- **Primary criteria:** dependency modeling, retry semantics, local UX, operational overhead
- **Selected:** Dagster (see `docs/EVOLVING_PLAN.md` Phase 3)
- **Implemented scope:** software-defined assets, asset job, weekday schedule, freshness sensor, asset check, Docker Compose services (`dagster-webserver`, `dagster-daemon`)

### Runtime scope
- **Candidate options:** keep script as fallback vs full orchestrator migration
- **Primary criteria:** migration risk, onboarding speed, troubleshooting complexity
- **Selected:** keep script fallback in v2 (`make pipeline-v1` / `make pipeline-legacy` / `PIPELINE_MODE=v1`)

### Storage choice
- **Selected:** PostgreSQL-backed Dagster instance storage (`dagster_storage`)
- **Alternatives considered:** default SQLite/volume-only storage
- **Why selected:** run/event history durability across restarts and closer parity with other stateful services
- **Trade-off accepted:** tighter dependency on PostgreSQL service health

### Decision snapshot
- **Selected direction:** Dagster orchestration with temporary legacy-script compatibility.
- **Rationale:** enables lineage/scheduling and asset-native retries while preserving rollback and local reliability.
- **Accepted trade-off:** short-term dual-path complexity in Makefile/ops workflow.
- **ADR reference:** `docs/decisions/ADR-006-v2-dagster-orchestration.md`

## 3) v2.5 reference extension (implemented)

### Iceberg for Gold
- **Selected:** Trino-managed Iceberg table for `ecb_dax_features` in catalog `iceberg`, backed by the same Hive Metastore; Parquet files remain the staging write path from Python.
- **Alternatives considered:** PyIceberg-only writes without Trino CTAS; full Silver migration to Iceberg in one step.
- **Why selected:** minimal change to ingestion code while demonstrating table-format semantics and SQL-accessible snapshots.
- **Reference:** `docs/decisions/ADR-013-iceberg-gold-trino.md`

### OpenMetadata as optional profile
- **Selected:** Compose overlay profile `openmetadata` with Collate OpenMetadata 1.5.x images, pipeline client disabled (no bundled Airflow).
- **Alternatives considered:** mandatory catalog in default stack; documentation-only without runnable compose.
- **Why selected:** keeps default footprint small while providing a realistic catalog UI for Trino metadata discovery.
- **Reference:** `docs/decisions/ADR-014-openmetadata-optional-profile.md`

### Superset as optional profile
- **Selected:** Compose overlay profile `superset` with a local Superset image that preinstalls the Trino SQLAlchemy driver and bootstraps two Trino connections.
- **Alternatives considered:** leave BI exploration to external desktop tools only; make Superset part of the default stack.
- **Why selected:** gives a browser-based SQL / dashboard path without increasing the default stack footprint or changing the core query engine.
- **Reference:** `docker/docker-compose.superset.yml`

## 4) v3 architecture decision frame (to fill during planning)

### Infrastructure target
- **Candidate options:** Kubernetes + Helm + Terraform, managed cloud stack, hybrid approach
- **Primary criteria:** reproducibility, operational burden, cost, team skill profile

### State and metadata portability
- **Candidate options:** managed services vs self-hosted parity
- **Primary criteria:** lock-in risk, disaster recovery, migration complexity

## 5) Planning method for future versions

For each major version, document decisions with this structure:

1. **Problem statement:** what scaling/usability gap vN must close
2. **Options matrix:** at least 2-3 viable paths
3. **Selection criteria:** performance, complexity, cost, onboarding, failure modes
4. **Decision and rationale:** why this path now
5. **Rollback strategy:** how to recover if choice underperforms
6. **Revisit trigger:** explicit condition that reopens this decision later
