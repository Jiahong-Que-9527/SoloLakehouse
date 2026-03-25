# TASKS.md — Development Backlog for SoloLakehouse

**Roadmap (versions):** [docs/roadmap.md](docs/roadmap.md) · **Detailed tasks:** [docs/EVOLVING_PLAN.md](docs/EVOLVING_PLAN.md)

This file tracks planned work, known issues, and improvement ideas.
AI coding agents should read this to understand what needs to be done
and avoid duplicating completed work.

Last updated: 2026-03-13

---

## Toward v1.0

### Known Issues

- [ ] `make up` uses a fixed `sleep 15` — on slow machines services may
      not be ready. **Fixed:** replaced with `minio-init` container that
      uses `depends_on: service_healthy`.
- [ ] `init-minio.sh` requires `mc` (MinIO Client) to be installed on the
      host. **Fixed:** bucket init now runs inside a `minio/mc` Docker
      container (`minio-init` service in docker-compose).
- [ ] No graceful handling if ECB SDW API is temporarily unavailable during
      `make pipeline` — the pipeline fails immediately. Add retry with backoff
      at the pipeline orchestration level.

### Test Coverage Gaps

- [ ] No tests for `scripts/run-pipeline.py` (orchestration logic)
- [ ] No tests for `scripts/verify-setup.py` (health checks)
- [ ] No tests for `ml/evaluate.py` (MLflow experiment runner)
- [ ] No integration tests (all current tests mock external services)
- [ ] No test for `silver_to_gold_features.py` edge cases (e.g., no
      matching DAX data for an ECB event)
- [ ] Add pytest-cov reporting to CI (`--cov=ingestion --cov=transformations --cov=ml`)

### Code Quality

- [ ] Add linting to CI: `ruff check .` or `flake8`
- [ ] Add formatting to CI: `ruff format --check .` or `black --check .`
- [ ] Add type checking: `mypy ingestion/ transformations/ ml/`
- [ ] Consider adding `py.typed` marker and stricter type annotations

### Documentation

- [ ] Add docstring to `ingestion/quality/bronze_checks.py` module
- [ ] Add inline comments to `silver_to_gold_features.py` explaining the
      event-study window logic

---

## v2.0 — Orchestrated Platform (Planned)

### Orchestration

- [ ] Replace linear `scripts/run-pipeline.py` with **Dagster** DAG
  - Define assets for each Medallion layer
  - Add retry policies per step
  - Add scheduling (e.g., daily ingestion)
  - Dagster UI for pipeline monitoring

### Self-Serve Usability (No-Author Operation)

- [ ] Make first-run success “self-serve”: ensure the path `make up` → `make verify` → `make pipeline` is reliable and well-documented
- [ ] Add a concise troubleshooting index (common failures → fixes) and link it from the Quick Start
- [ ] Add “release/upgrade” guidance (what changes between versions, how to migrate configs/data)

### Observability

- [ ] Add **Prometheus** with custom application metrics:
  - `pipeline_ingestion_duration_seconds`
  - `pipeline_data_quality_score` (valid / total records)
  - `pipeline_silver_row_count`
  - `mlflow_training_duration_seconds`
- [ ] Add **Grafana** dashboards for pipeline health
- [ ] Expose Trino JMX metrics to Prometheus
- [ ] Add alerting rules (e.g., quality score < 0.95)

### Data

- [ ] Add streaming ingestion path (Kafka / Redpanda → Bronze)
- [ ] Add Feature Store (Feast) for ML feature serving
- [ ] Add more data sources (e.g., Fed Funds rate, S&P 500)
- [ ] Consider Delta Lake or Apache Iceberg for ACID on Silver/Gold layers

### Infrastructure

- [ ] Add **CloudBeaver** as optional web SQL IDE
- [ ] Separate dev/prod Docker Compose profiles
- [ ] Add health-check-based `make up` (replace `sleep 15` with polling)

---

## v3.0 — Production Infrastructure (Planned)

- [ ] Migrate from Docker Compose to **Kubernetes** (Helm charts)
- [ ] Add **Terraform** for cloud provisioning (AWS/GCP)
- [ ] Add CI/CD pipeline: build → test → deploy (GitHub Actions)
- [ ] Add secrets management (Vault or cloud-native)
- [ ] Add autoscaling for Trino workers
- [ ] Add backup/restore for MinIO and PostgreSQL
- [ ] Multi-environment support (dev / staging / prod)

---

## Ideas (Unscoped)

- [ ] Jupyter notebook integration for interactive exploration
- [ ] dbt for SQL-based transformations (Silver → Gold alternative)
- [ ] Great Expectations for data quality (replace custom checks)
- [ ] Model serving endpoint (MLflow + FastAPI or BentoML)
- [ ] Data lineage tracking / data catalog (OpenMetadata or DataHub)
- [ ] Add a second ML use case (e.g., time-series forecasting with Prophet)
