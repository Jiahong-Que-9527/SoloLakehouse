# SoloLakehouse Evolving Plan: v1.0 → v2.0

> **Navigation:** For the consolidated roadmap (tables and v1+ milestones), see [roadmap.md](roadmap.md). This file is a **step-by-step task list** for implementers and coding agents.

> This is an agent-executable task list. Each item is a self-contained unit of work.
> Work through items in order within each phase. Items marked with `[depends: N]` must come after item N.
>
> **History tracking is mandatory for every major version**: when a version phase is completed, update `docs/history/timeline.md` and `docs/history/architecture-evolution.md`, and create/update a version planning file from `docs/history/planning-template.md`.

---

## Phase 1: Ingestion hardening

Goal: Make the pipeline resilient to real-world failures. No orchestration changes yet — just harden the existing linear pipeline.

---

### 1.1 Pipeline-Level Error Handling & Retry

- [x] **Task 1**: Add a `StepError` exception class to `scripts/run-pipeline.py`. Wrap each of the 6 pipeline steps in a try/except block. On failure: log the step name + error with structlog, raise `StepError` with step metadata (step number, name, original exception). Ensure the pipeline exits with code 1 and prints a clear "PIPELINE FAILED at step X" message.

- [x] **Task 2**: Add pipeline-level retry to `scripts/run-pipeline.py`. Steps 1 (ECB collection) and 2 (DAX collection) should retry up to 3 times with 5-second delays on `StepError`. Steps 3–6 (transformations, ML) should NOT retry automatically. Use a `retry_step(fn, max_attempts, delay)` helper function.

- [x] **Task 3**: Add a circuit breaker flag to `ingestion/collectors/ecb_collector.py`. If all 3 HTTP retries are exhausted, raise a `CollectorUnavailableError` (new custom exception in `ingestion/exceptions.py`). The `run-pipeline.py` orchestrator should catch this and log a distinct "upstream API unavailable" message (different from a data validation failure).

### 1.2 Incremental Ingestion

- [x] **Task 4**: Add a `last_ingested_date` check to `ingestion/collectors/ecb_collector.py`. Before writing, list existing objects in `bronze/ecb_rates/` from MinIO and find the latest `ingestion_date=YYYY-MM-DD` partition. If today's date partition already exists, skip the write and log `ecb_already_ingested_today`. Return early with `{"status": "skipped", "reason": "already_ingested_today"}`.

- [x] **Task 5**: Same incremental check for `ingestion/collectors/dax_collector.py`. Check for existing `bronze/dax_daily/ingestion_date=YYYY-MM-DD/` partition. If found, skip and log `dax_already_ingested_today`.

- [x] **Task 6**: Add an `--force` flag to `scripts/run-pipeline.py` (argparse). When `--force` is passed, bypass the incremental skip logic in both collectors and re-ingest even if data for today already exists. Document in Makefile: `make pipeline ARGS="--force"`.

### 1.3 Richer Quality Checks

- [x] **Task 7**: Add `check_no_future_dates(df, date_col)` to `ingestion/quality/bronze_checks.py`. Raises `ValueError` if any date in `date_col` is later than today (`datetime.date.today()`). Add to both `run_ecb_bronze_checks()` and `run_dax_bronze_checks()`.

- [x] **Task 8**: Add `check_date_continuity(df, date_col, max_gap_days)` to `ingestion/quality/bronze_checks.py`. Raises `ValueError` if any gap between consecutive dates exceeds `max_gap_days`. For ECB: `max_gap_days=180` (policy meetings are ~6 weeks apart). For DAX: `max_gap_days=5` (weekends + holidays). Wire into `run_ecb_bronze_checks()` and `run_dax_bronze_checks()`.

- [x] **Task 9**: Add `check_schema_version(df, expected_columns)` to `ingestion/quality/bronze_checks.py`. Raises `ValueError` if `df.columns` is missing any column from `expected_columns`. Wire into both bronze check runners to verify all expected columns are present after ingestion.

- [x] **Task 10**: Add a Silver-layer quality report function `run_silver_quality_report(df, layer_name) -> dict` to a new file `transformations/quality_report.py`. It should return a dict with: `row_count`, `null_counts_per_column`, `date_range`, `duplicate_count`. Call this function at the end of each `run()` function in the three transformation files and log the result with structlog. Do NOT raise on warnings — just log.

### 1.4 Dead-Letter Queue for Rejected Records

- [x] **Task 11**: Modify `ingestion/bronze_writer.py` to accept a `rejected_records: list[dict]` parameter in its `write()` method (or a new `write_rejected()` method). Write rejected records to `bronze/rejected/source=ECB/ingestion_date=YYYY-MM-DD/rejected.parquet` (or DAX). Each rejected record should include: original data + `rejection_reason` column (the Pydantic validation error message). Use the same MinIO/PyArrow pattern.

- [x] **Task 12** [depends: Task 11]: Update `ingestion/collectors/ecb_collector.py` and `dax_collector.py` to pass rejected records to `bronze_writer.write_rejected()`. Log counts: `ecb_ingestion_complete`, with fields `valid_count`, `rejected_count`, `rejected_path` (or `null` if no rejections).

### 1.5 Test Coverage Improvements

- [x] **Task 13**: Add tests for the new `check_no_future_dates` and `check_date_continuity` quality check functions in `tests/test_quality_checks.py`. At least 2 test cases each: one passing, one failing with the expected `ValueError`.

- [x] **Task 14**: Add tests for `check_schema_version` in `tests/test_quality_checks.py`. Test: correct columns pass, missing column fails with descriptive error.

- [x] **Task 15**: Add tests for the `write_rejected()` method in `tests/test_bronze_writer.py`. Test: rejected records written with correct path and `rejection_reason` column present.

- [x] **Task 16**: Add a test class `TestPipelineRetry` in a new file `tests/test_pipeline.py`. Mock the collector and verify: (a) pipeline retries failed steps up to 3 times; (b) pipeline raises `StepError` after max retries exceeded; (c) `--force` flag bypasses incremental skip. Use `unittest.mock.patch`.

---

## Phase 2: v1.0 — Effortless Deployment

Goal: Anyone can clone the repo and run `make up && make verify && make pipeline` successfully on first try. Every failure produces a clear, actionable error message.

---

### 2.1 Reliable Health Checks for All Services

- [x] **Task 17**: Add Docker health checks to `docker/docker-compose.yml` for the three services that currently lack them:
  - **hive-metastore**: `test: ["CMD", "bash", "-c", "echo 'status' | nc -w 2 localhost 9083 || exit 1"]` (TCP probe on Thrift port 9083), interval 15s, retries 5, start_period 60s.
  - **trino**: `test: ["CMD", "curl", "-f", "http://localhost:8080/v1/info"]`, interval 15s, retries 10, start_period 90s.
  - **mlflow**: `test: ["CMD", "curl", "-f", "http://localhost:5000/health"]`, interval 15s, retries 5, start_period 30s.

- [x] **Task 18** [depends: Task 17]: Update `depends_on` conditions in `docker/docker-compose.yml` to use `condition: service_healthy` (not just `service_started`) for all service dependencies. Specifically: trino should wait for hive-metastore to be healthy; minio-init should already depend on minio being healthy (verify this is correct).

- [x] **Task 19** [depends: Task 18]: Update `scripts/verify-setup.py` to add health checks for hive-metastore and MLflow that were previously missing or weak. For each service add: timeout handling (5s per check), a distinct exit code per failing service (not just global exit 1), and a `PASS`/`FAIL`/`TIMEOUT` status prefix in output. Final output: a summary table of all 5 services with their status.

### 2.2 One-Command Setup Reliability

- [x] **Task 20**: Add a `make setup` target to the `Makefile` that: (1) checks Docker is running (`docker info`), (2) checks `.env` file exists (copy from `.env.example` if missing), (3) runs `docker compose pull` to pre-pull images, (4) runs `make up`. Print a clear step-by-step status for each action. This is the recommended first-run command.

- [x] **Task 21**: Add a `.env.example` file to the repository root (if not already present with all variables) containing all required environment variables with safe default values. Add a validation step in `scripts/verify-setup.py` that checks all required env vars are set and prints which ones are missing if not.

- [x] **Task 22**: Add a `make wait` target to the `Makefile` that polls `scripts/verify-setup.py` every 10 seconds until all services are healthy, with a 5-minute timeout. Print progress dots during wait. Use this in `make up` after starting containers: `make up` = `docker compose up -d && make wait`.

### 2.3 Linting and Type Checking in CI

- [x] **Task 23**: Add `ruff` to `requirements.txt` (pin to `ruff==0.4.4`). Create a `ruff.toml` (or `[tool.ruff]` section in `pyproject.toml`) at the project root with: `line-length = 100`, `select = ["E", "F", "I"]` (errors, pyflakes, isort). Run `ruff check .` locally and fix all existing violations.

- [x] **Task 24** [depends: Task 23]: Add a `make lint` target to `Makefile` that runs `ruff check .`. Add a lint job to `.github/workflows/test.yml` that runs `make lint` as a separate step before tests. CI should fail if linting fails.

- [x] **Task 25**: Add `mypy` to `requirements.txt` (pin to `mypy==1.10.0`). Create a `mypy.ini` at project root with: `python_version = 3.11`, `ignore_missing_imports = True`, `strict = False`, `check_untyped_defs = True`. Add type annotations to all public function signatures in `ingestion/`, `transformations/`, and `ml/` (parameters + return types). Run `mypy .` and fix all errors.

- [x] **Task 26** [depends: Task 25]: Add a `make typecheck` target to `Makefile` that runs `mypy .`. Add a typecheck job to `.github/workflows/test.yml` as a separate step.

### 2.4 Test Coverage Reporting

- [x] **Task 27**: Enable pytest-cov in CI. Update `.github/workflows/test.yml` test command to: `pytest tests/ -v --tb=short --cov=ingestion --cov=transformations --cov=ml --cov-report=term-missing --cov-fail-under=70`. The build should fail if coverage drops below 70%.

- [x] **Task 28**: Add a `make test-cov` target to `Makefile` that runs pytest with coverage report. Add a `make test-cov-html` target that generates an HTML coverage report in `htmlcov/`. Add `htmlcov/` and `.coverage` to `.gitignore`.

### 2.5 Integration Tests

- [x] **Task 29**: Create `tests/integration/` directory with a `conftest.py` that: (a) checks if Docker services are running (skip all integration tests if not), (b) provides a `minio_client` fixture connecting to real MinIO at `localhost:9000`, (c) provides a `test_bucket` fixture that creates/destroys a `sololakehouse-test` bucket per test session.

- [x] **Task 30** [depends: Task 29]: Add `tests/integration/test_bronze_writer_integration.py`. Tests: (a) write a small DataFrame to real MinIO and read it back; (b) idempotent write produces same object; (c) rejected records written to correct path. Mark with `@pytest.mark.integration`.

- [x] **Task 31** [depends: Task 29]: Add `tests/integration/test_pipeline_smoke.py`. A single smoke test: run `run-pipeline.py` end-to-end against real services, verify Gold parquet exists in MinIO, verify row count > 0. Mark with `@pytest.mark.integration`. Add `make test-integration` target to Makefile.

### 2.6 Clear Troubleshooting & Documentation

- [x] **Task 32**: Update `docs/deployment.md` with a "Troubleshooting" section that covers the top 5 failure modes observed in practice:
  1. `hive-metastore` fails to start (PostgreSQL not ready) — solution: `make clean && make up`
  2. `trino` returns "catalog not available" — solution: wait 60s for hive-metastore, check `make verify`
  3. ECB API timeout during `make pipeline` — solution: retry with `make pipeline`; ECB API is rate-limited
  4. MinIO bucket already exists error — solution: safe to ignore; minio-init is idempotent
  5. `mlflow` UI shows no experiments — solution: run `make pipeline` first; experiments auto-created

- [x] **Task 33**: Update `README.md` to add a "Quick Validation" section after "Quick Start". Show expected output of `make verify` when all services are healthy (copy the actual output format from `verify-setup.py`). Add a "Common Issues" link pointing to `docs/deployment.md#troubleshooting`.

- [x] **Task 34**: Add a `CHANGELOG.md` at the project root. Create entries for v1.0 (initial complete release) and subsequent versions as needed. Use Keep a Changelog format: Added / Changed / Fixed sections per version.

### 2.7 v1.0 Release Validation

- [x] **Task 35**: Create a `docs/V1_RELEASE_CHECKLIST.md` with the following items to verify manually before tagging v1.0:
  - [ ] `make clean && make up` completes without errors on a fresh machine
  - [ ] `make verify` shows all 5 services as PASS
  - [ ] `make pipeline` runs end-to-end without errors
  - [ ] `make test` passes (≥70% coverage)
  - [ ] `make lint` passes
  - [ ] `make typecheck` passes
  - [ ] MLflow UI at `http://localhost:5000` shows experiment results
  - [ ] Trino query `SELECT * FROM hive.default.ecb_rates_cleaned LIMIT 5` returns rows
  - [ ] `docker compose down && docker compose up -d` (restart) preserves all data

- [x] **Task 36** [depends: Task 35]: Once all items in `V1_RELEASE_CHECKLIST.md` are verified, update `README.md` version badge and `CLAUDE.md` Roadmap table to mark v1.0 as "current". Update the `docker/docker-compose.yml` image labels. Tag the git commit as `v1.0.0`.

---

## Phase 3: v2.0 — Orchestrated Platform

Goal: Replace the linear `run-pipeline.py` script with a proper DAG orchestrator (Dagster). Enable scheduling, retries-per-asset, and a visual pipeline UI.

---

### 3.1 Dagster Project Setup

- [x] **Task 37**: Add Dagster dependencies to a new `requirements-dagster.txt` file (keep separate from core `requirements.txt` to avoid version conflicts): `dagster==1.7.*`, `dagster-webserver==1.7.*`, `dagster-aws==0.23.*` (for MinIO/S3), `dagster-docker==0.23.*`. Add a `make dagster-install` target.

- [x] **Task 38** [depends: Task 37]: Create a `dagster/` directory at the project root. Inside: `dagster/__init__.py`, `dagster/assets.py`, `dagster/resources.py`, `dagster/definitions.py`, `dagster/workspace.yaml`. This is the Dagster project scaffold. Do not implement asset logic yet.

- [x] **Task 39** [depends: Task 38]: Define Dagster resources in `dagster/resources.py`:
  - `MinioResource`: wraps `minio.Minio` client; reads endpoint/credentials from env vars (same as current pattern)
  - `PipelineConfigResource`: wraps the config dict currently passed to collectors
  Both should use `@dagster.ConfigurableResource`.

### 3.2 Define Dagster Software-Defined Assets

- [x] **Task 40** [depends: Task 39]: Create the Bronze layer assets in `dagster/assets.py`:
  - `ecb_bronze`: calls `ECBCollector.collect()`. Metadata: row count, partition date, rejection count.
  - `dax_bronze`: calls `DAXCollector.collect()`. Same metadata.
  Both are `@asset` with `group_name="bronze"`, `retry_policy=RetryPolicy(max_retries=3, delay=5)`.

- [x] **Task 41** [depends: Task 40]: Create the Silver layer assets in `dagster/assets.py`:
  - `ecb_silver`: calls `ecb_bronze_to_silver.run()`. Depends on `ecb_bronze`. Metadata: row count, silver path.
  - `dax_silver`: calls `dax_bronze_to_silver.run()`. Depends on `dax_bronze`. Same metadata.
  Both with `group_name="silver"`, no auto-retry (deterministic transforms).

- [x] **Task 42** [depends: Task 41]: Create the Gold layer asset and ML asset in `dagster/assets.py`:
  - `gold_features`: calls `silver_to_gold_features.run()`. Depends on `ecb_silver` AND `dax_silver`. Metadata: event count.
  - `ml_experiment`: calls `ml/evaluate.py run_experiment_set()`. Depends on `gold_features`. Metadata: best model accuracy, experiment ID.
  Both with appropriate group names ("gold", "ml").

### 3.3 Dagster Job & Schedule

- [x] **Task 43** [depends: Task 42]: Define a `full_pipeline_job` in `dagster/definitions.py` that materializes all assets in dependency order: `ecb_bronze` → `dax_bronze` → `ecb_silver` → `dax_silver` → `gold_features` → `ml_experiment`. Wire in `MinioResource` and `PipelineConfigResource`.

- [x] **Task 44** [depends: Task 43]: Add a `@schedule` named `daily_pipeline_schedule` in `dagster/definitions.py` that runs `full_pipeline_job` at 06:00 UTC every weekday (cron: `"0 6 * * 1-5"`). Use `@schedule(cron_schedule=..., job=..., execution_timezone="UTC")`.

- [x] **Task 45** [depends: Task 44]: Register everything in `dagster/definitions.py` as a `Definitions` object: assets, jobs, schedules, resources. Create `dagster/workspace.yaml` pointing to this `Definitions` object. Test with `dagster asset list` (should list all 6 assets).

### 3.4 Dagster in Docker Compose

- [x] **Task 46** [depends: Task 45]: Create `docker/dagster/Dockerfile` based on `python:3.11-slim`. Install both `requirements.txt` and `requirements-dagster.txt`. Copy the `dagster/` project directory and all source code (`ingestion/`, `transformations/`, `ml/`, `scripts/`). Set entrypoint to `dagster-webserver`.

- [x] **Task 47** [depends: Task 46]: Add two new services to `docker/docker-compose.yml`:
  - `dagster-webserver`: runs `dagster-webserver -h 0.0.0.0 -p 3000`, port 3000, depends on minio and postgres being healthy.
  - `dagster-daemon`: runs `dagster-daemon run` (required for schedules and sensors), same image, same depends_on.
  Add `dagster-storage` volume for Dagster's run history SQLite DB (or point to the existing postgres with a `dagster` database).

- [x] **Task 48** [depends: Task 47]: Add PostgreSQL database for Dagster run storage. Update `config/postgres/init.sql` to also `CREATE DATABASE dagster_storage;`. Update `dagster/workspace.yaml` to use PostgreSQL as the run storage and event log storage (not SQLite). This enables persistent run history across container restarts.

### 3.5 Migrate from run-pipeline.py to Dagster

- [x] **Task 49** [depends: Task 45]: Keep `scripts/run-pipeline.py` working but add a deprecation warning: "This script is deprecated in v2.0. Use `dagster job execute -j full_pipeline_job` or the Dagster UI instead." Do NOT remove the script — it's useful for quick local runs without the Dagster daemon.

- [x] **Task 50** [depends: Task 47]: Update `Makefile`:
  - `make pipeline`: now runs `dagster job execute -j full_pipeline_job` (requires Dagster services up)
  - `make pipeline-legacy`: runs the old `scripts/run-pipeline.py` directly
  - `make dagster-ui`: opens browser to `http://localhost:3000`
  - `make up`: now starts all 8 services including dagster-webserver and dagster-daemon

### 3.6 Sensors & Alerting

- [x] **Task 51** [depends: Task 45]: Add a `@sensor` named `ecb_data_freshness_sensor` in `dagster/assets.py`. It checks if the latest `bronze/ecb_rates/` partition in MinIO is older than 48 hours. If so, it emits a `RunRequest` to trigger `ecb_bronze` re-materialization. Tick interval: every 30 minutes.

- [x] **Task 52** [depends: Task 45]: Add a `@asset_check` for `gold_features` in `dagster/assets.py`. The check verifies that `gold_features` has at least 10 rows (event-study requires minimum data). If it fails, the check status is `FAILED` with a descriptive message. This replaces the silent "< 3 pre-event days" log.

### 3.7 Observability (Basic)

- [x] **Task 53**: Add `StatsD`-compatible metric emission to `scripts/run-pipeline.py` (and the Dagster assets). After each step, emit timing metrics using Python's `time.perf_counter()`. Write metrics to a structured log line: `{"metric": "pipeline.step.duration_ms", "step": "ecb_bronze", "value": 1234}`. No Prometheus setup yet — just emit to structlog so they're queryable from logs.

- [x] **Task 54**: Add a `dagster/io_managers.py` with a custom `ParquetIOManager` that extends Dagster's `UPathIOManager`. It should handle reading/writing Parquet files to MinIO automatically based on asset key (so assets can yield DataFrames directly without calling `bronze_writer.py` manually). This decouples I/O from business logic. Mark this as OPTIONAL — implement only if the asset pattern needs cleaner I/O abstraction.

### 3.8 Documentation Updates for v2.0

- [x] **Task 55** [depends: Task 50]: Add `docs/DAGSTER_GUIDE.md` explaining:
  - How to access the Dagster UI (`http://localhost:3000`)
  - How to manually trigger a pipeline run from the UI
  - How to view asset lineage (the dependency graph)
  - How to enable/disable the daily schedule
  - How to re-run a failed step without re-running the whole pipeline
  - Difference between `make pipeline` (Dagster) and `make pipeline-legacy` (script)

- [x] **Task 56** [depends: Task 44]: Update `docs/architecture.md` to add a "Orchestration Layer" section describing the Dagster DAG, asset dependencies, and schedule. Include the asset dependency graph in text/ASCII form.

- [x] **Task 57** [depends: Task 36, Task 56]: Update `CLAUDE.md` Roadmap table to mark v2.0 as "current". Update the Tech Stack table to include Dagster. Update the Commands section with new `make` targets. Tag git commit as `v2.0.0`.

- [x] **Task 58** [depends: Task 57]: Update history records in `docs/history/` for v2.0:
  - add v2.0 milestone outcome and next gate in `docs/history/timeline.md`
  - record v2.0 architecture decisions/trade-offs in `docs/history/architecture-evolution.md`
  - create/update `docs/history/v2-planning.md` from `docs/history/planning-template.md` with final decision notes and carry-forward items

---

## Summary of New Files Created

| File | Phase | Purpose |
|------|-------|---------|
| `ingestion/exceptions.py` | Phase 1 | Custom exception classes |
| `transformations/quality_report.py` | Phase 1 | Silver-layer quality reporting |
| `tests/test_pipeline.py` | Phase 1 | Pipeline retry/orchestration tests |
| `tests/integration/conftest.py` | v1.0 | Integration test fixtures |
| `tests/integration/test_bronze_writer_integration.py` | v1.0 | Bronze writer integration tests |
| `tests/integration/test_pipeline_smoke.py` | v1.0 | End-to-end smoke test |
| `ruff.toml` | v1.0 | Linting configuration |
| `mypy.ini` | v1.0 | Type checking configuration |
| `CHANGELOG.md` | v1.0 | Version history |
| `docs/V1_RELEASE_CHECKLIST.md` | v1.0 | Release validation checklist |
| `dagster/__init__.py` | v2.0 | Dagster project init |
| `dagster/assets.py` | v2.0 | Software-defined assets |
| `dagster/resources.py` | v2.0 | Dagster resource definitions |
| `dagster/definitions.py` | v2.0 | Dagster Definitions object |
| `dagster/workspace.yaml` | v2.0 | Dagster workspace config |
| `dagster/io_managers.py` | v2.0 | Custom MinIO Parquet IO manager (optional) |
| `docker/dagster/Dockerfile` | v2.0 | Dagster container image |
| `requirements-dagster.txt` | v2.0 | Dagster dependency lockfile |
| `docs/DAGSTER_GUIDE.md` | v2.0 | Dagster usage documentation |

## Summary of Modified Files

| File | Phase | Change |
|------|-------|--------|
| `scripts/run-pipeline.py` | Phase 1 | StepError, retry logic, --force flag |
| `ingestion/collectors/ecb_collector.py` | Phase 1 | CollectorUnavailableError, incremental skip, rejected write |
| `ingestion/collectors/dax_collector.py` | Phase 1 | Incremental skip, rejected write |
| `ingestion/bronze_writer.py` | Phase 1 | write_rejected() method |
| `ingestion/quality/bronze_checks.py` | Phase 1 | 3 new check functions |
| `transformations/ecb_bronze_to_silver.py` | Phase 1 | Call quality_report at end of run() |
| `transformations/dax_bronze_to_silver.py` | Phase 1 | Call quality_report at end of run() |
| `transformations/silver_to_gold_features.py` | Phase 1 | Call quality_report at end of run() |
| `tests/test_quality_checks.py` | Phase 1 | Tests for 3 new check functions |
| `tests/test_bronze_writer.py` | Phase 1 | Tests for write_rejected() |
| `docker/docker-compose.yml` | v1.0 + v2.0 | Health checks for all services; Dagster services |
| `scripts/verify-setup.py` | v1.0 | Timeout handling, per-service status, summary table |
| `Makefile` | v1.0 + v2.0 | setup, wait, lint, typecheck, test-cov, dagster targets |
| `.github/workflows/test.yml` | v1.0 | Lint + typecheck + coverage jobs |
| `config/postgres/init.sql` | v2.0 | CREATE DATABASE dagster_storage |
| `requirements.txt` | v1.0 | Add ruff, mypy |
| `README.md` | v1.0 + v2.0 | Quick validation section, v2.0 architecture |
| `docs/deployment.md` | v1.0 | Troubleshooting section |
| `docs/architecture.md` | v2.0 | Orchestration layer section |
| `CLAUDE.md` | v2.0 | Updated roadmap, tech stack, commands |
