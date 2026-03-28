# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [v2.5.0] - 2026-03-28 (reference extension)

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
- `make pipeline` defaults to v2 Dagster path; `make pipeline PIPELINE_MODE=v1` retains legacy compatibility.
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
