# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
