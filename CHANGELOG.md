# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed
- Dagster GraphQL adapter no longer references the removed
  `EventTextMetadataEntry` type (Dagster 1.12), which blocked automatic and
  manual lineage evidence collection.
- `lineage_evidence_sensor` defaults to `RUNNING`, yields an explicit skip reason
  after emission, and monitors all code locations so workspace-launched runs
  trigger evidence emission.
- `make pipeline` / `make demo` now launch jobs through the Dagster workspace
  (with `scripts/wait-for-dagster-run.py`) so runs carry a repository origin.
- `scripts/init-minio.sh` no longer depends on `grep` inside the MinIO `mc`
  image and recognizes the actual Object Lock JSON shape from `mc stat --json`.

### Added
- Dagster `lineage_evidence_sensor` emits lineage evidence automatically when a
  governed asset materializes in a successful run, replacing the manual CLI with
  a hand-copied Dagster run ID for the default pipeline path.
- MinIO Object Lock on the audit bucket (`GOVERNANCE`, default retention
  `2555d`), verified by `make verify` through the MinIO API.
- Causal snapshot↔run binding: governed Dagster materializations stamp
  `iceberg_snapshot_id` metadata, and `LineageEvidenceJoiner` rejects a mismatch
  with the current Iceberg snapshot.
- CI and `make test-cov` now include `governance/` and `dagster/` in the
  coverage gate.
- Unit tests for `dagster/assets.py` and automatic lineage-evidence emission.

### Remaining v2.6.1 acceptance gate
- External validator sign-off in
  `docs/external-validation/v2.6.1-external-validation.md` (gate added; record
  open).

## [v2.6.1] - 2026-07-31

### Fixed
- `RUNTIME_VERSION` now matches the released version (`slh-v2.6.1`). In
  `v2.6.0` it defaulted to `slh-v2.5.1`, and because `runtime_version` is a
  required field of every `LineageRecord`, all governance evidence produced by
  that release recorded the wrong runtime version. The release drill was re-run
  and the manifest read back to confirm the corrected value; see
  `docs/v2.6-release-readiness.md`.

### Changed
- The published repository is **English-only**. Chinese working documents are
  maintained locally under `docs/local-cn/` and excluded from publication.
- `docs/roadmap.md` and `TASKS.md` are the sole authorities for version scope
  and execution order. Conflicting 2026-05-05 planning notes are superseded and
  no longer published.
- Planning now uses measured delivery velocity rather than optimistic estimates,
  and publishes version **order** rather than dates.
- Recorded decisions D1 (v2.7/v2.8 ordering, provisionally v2.8 first pending
  external input), D2 (entity split deferred indefinitely), and D3
  (portal/Keycloak is sandbox-only).
- Release readiness now requires **external validation**: at least one person
  outside the project runs `make setup` and the version's core command on their
  own machine.

### Added
- `AGENTS.md` is now the shared, tool-neutral contract for every agent working
  in this repository: authority chain, current version state, decision gates,
  hard rules, validation commands, and repository map.
- `.cursor/rules/sololakehouse.mdc` — Cursor previously had no project entry
  point and began every session without the roadmap or baseline constraints.
- `scripts/check-agent-docs.py` and `make check-agent-docs`, wired into CI:
  fails the build when an agent entry point goes missing, stops pointing at the
  contract, or starts duplicating version state.
- v2.6.1 scope defined in `TASKS.md` as Blocks `R` and `J`.

## [v2.6.0] - 2026-07-31

### Added
- v2.6 dataset contracts, governed quality checks, three-source lineage
  evidence adapters, canonical SHA-256 manifests, and audit-bucket output via
  `make lineage-evidence`.
- v2.6 release readiness gate requiring one complete OpenMetadata, Iceberg, and
  Dagster evidence drill for the governed Gold dataset.

### Known limitations
- The v2.6 evidence command requires a pre-ingested OpenMetadata Trino table,
  a local-only read token, a successful Dagster materialization, and a current
  Iceberg snapshot. It intentionally emits no partial artifact when any source
  is unavailable.
- Audit output is a stable object layout and canonical manifest, not an Object
  Lock/WORM retention implementation, automated catalog ingestion, production
  RBAC, or a regulatory-compliance claim.
- Evidence generation is **operator-triggered**, not automatic: it requires a
  Dagster run ID supplied by hand. Automatic emission is deferred to v2.6.1.
- One governed dataset (`fin.ecb_dax_features_gold`) has a recorded drill; the
  other four contracts exist but have not produced evidence. Deferred to v2.6.1.
- The three-source join verifies that names are consistent across sources, but
  does **not** verify that the Iceberg snapshot was produced by the referenced
  Dagster run. Causal binding is deferred to v2.6.1.

### Changed
- Standardized runtime to a single v2.5 execution path (`make pipeline` via Dagster only).
- Promoted OpenMetadata and Superset from optional profiles to default mandatory stack components.
- Updated verification/bootstrap/release docs to reflect v2.5 single-track operations.
- Local Compose durable state uses **bind mounts** under `docker/data/` (with `make prepare-data-dirs`) instead of Docker named volumes; `make clean` removes those directories and purges legacy named volumes when present.

### Known defect (fixed in v2.6.1)
- `RUNTIME_VERSION` defaults to `slh-v2.5.1` in this release, so every evidence
  manifest produced by `v2.6.0` records the wrong runtime version. Because
  `runtime_version` is a required field of `LineageRecord`, evidence generated
  from this tag misattributes itself to the previous runtime. Upgrade to
  `v2.6.1`, or set `RUNTIME_VERSION` explicitly in the environment.

### Fixed
- `scripts/bootstrap-postgres.py` verifies TCP PostgreSQL credentials after Docker-exec bootstrap and aligns the DB role password with `.env` when it has drifted from the data directory (avoids recurring Hive Metastore auth failures).

### Removed
- Legacy host-side pipeline entrypoint (`scripts/run-pipeline.py`).
- Legacy Makefile switches and targets (`PIPELINE_MODE`, `pipeline-v1`, `pipeline-legacy`).

## [v2.5.0] - 2026-03-28 (reference extension)

**Note (2026-04):** Subsequent mainline changes merged OpenMetadata and Superset into the default `make up` path (Compose is always stacked from the `Makefile`; profile-only `make up-openmetadata` / `make up-superset` targets were removed). Local persistence later moved from Docker named volumes to `docker/data/` bind mounts.

### Added
- Apache Iceberg Gold table via Trino (`iceberg.gold.ecb_dax_features_iceberg`) with Hive Metastore as the catalog backend (see [ADR-013](docs/decisions/ADR-013-iceberg-gold-trino.md)).
- Trino `iceberg` catalog configuration template (`config/trino/catalog/iceberg.properties`).
- Optional OpenMetadata 1.5.x compose profile (`make up-openmetadata`) for data catalog, metadata lineage, and Trino connector discovery (see [ADR-014](docs/decisions/ADR-014-openmetadata-optional-profile.md)).
- Optional Apache Superset 6.0.0 compose profile (`make up-superset`) with Trino SQLAlchemy support for SQL and dashboard exploration.
- Automatic Superset bootstrap for two Trino connections: `trino_iceberg_gold` and `trino_hive_default`.
- Integration test for Trino Iceberg table creation and query (`tests/integration/test_trino_iceberg.py`).
- `make verify-openmetadata` target for optional service health-check.
- `make verify-superset` target for optional Superset health-check.

## [v2.0.0] - 2026-03-28

### Added
- Dagster orchestration layer: six software-defined assets (`ecb_bronze`, `dax_bronze`, `ecb_silver`, `dax_silver`, `gold_features`, `ml_experiment`).
- `full_pipeline_job` Dagster job replacing the linear legacy script as the default execution path.
- `daily_pipeline_schedule` (weekdays 06:00 UTC) and `ecb_data_freshness_sensor` (30-minute interval).
- `gold_features_min_rows_check` asset check as a quality gate.
- Dagster webserver and daemon services in Docker Compose; `dagster_storage` PostgreSQL database.
- `dagster/io_managers.py` with `ParquetIOManager` for DataFrame-native asset experiments.
- `make pipeline` defaults to v2 Dagster path (legacy `PIPELINE_MODE` / script path removed in v2.5+).
- Bootstrap script (`scripts/bootstrap-postgres.py`) with Docker-exec and TCP fallback modes.

### Changed
- `make pipeline` now invokes Dagster job by default (was legacy script in v1).
- Harden integration test execution and local release bootstrap.

## [v1.0.0] - 2026-03-26

### Added
- Complete SoloLakehouse core stack with Docker Compose services:
  MinIO, PostgreSQL, Hive Metastore, Trino, and MLflow.
- Ingestion layer with schema validation, bronze quality checks, collectors, and rejected-record handling.
- Transformation layer for Bronze-to-Silver and Silver-to-Gold feature engineering.
- ML training and MLflow experiment evaluation modules.
- End-to-end pipeline and environment verification scripts.
- Unit and integration test scaffolding plus CI workflow for lint, typecheck, and tests.

### Changed
- Upgraded all dependencies to latest stable versions: MinIO RELEASE.2025-09-07,
  PostgreSQL 17, Trino 480, MLflow 3.10.1, PyArrow 23.0.1, Pydantic 2.12.5,
  XGBoost 3.2.0, scikit-learn 1.8.0, structlog 25.5.0, ruff 0.15.7, mypy 1.19.1.
- Standardized project quality tooling with Ruff and MyPy configuration files.
- Expanded repository documentation for deployment, quick validation, and troubleshooting.

### Fixed
- Improved pipeline reliability with retry handling for ingestion steps.
- Added explicit health and readiness checks to reduce startup ambiguity across services.
