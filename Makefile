.PHONY: up up-openmetadata up-superset down clean bootstrap-db reset-mlflow-db wait-postgres-ready pipeline pipeline-legacy pipeline-v1 pipeline-dagster verify verify-openmetadata verify-superset test test-cov test-cov-html test-integration release-check lint typecheck setup wait dagster-install dagster-ui

COMPOSE_FILE := docker/docker-compose.yml
COMPOSE_OM := -f docker/docker-compose.yml -f docker/docker-compose.openmetadata.yml
COMPOSE_SUPERSET := -f docker/docker-compose.yml -f docker/docker-compose.superset.yml
ENV_FILE ?= .env
DOCKER_COMPOSE := docker compose --env-file $(ENV_FILE)
PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
PIPELINE_MODE ?= v2
ARGS ?=
DAGSTER_JOB ?= full_pipeline_job
VERIFY_ENV ?=
SUPERSET_DB_NAME ?= superset_metadata

# Ensure required DBs exist before MLflow and other clients start (avoids race with bootstrap-db).
wait-postgres-ready:
	@echo "Waiting for PostgreSQL to accept connections..."
	@for i in $$(seq 1 90); do \
		docker exec slh-postgres sh -c 'pg_isready -U "$$POSTGRES_USER" -d postgres' >/dev/null 2>&1 && exit 0; \
		sleep 1; \
	done; \
	echo "Postgres did not become ready in time."; exit 1

up:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) up -d postgres minio
	$(MAKE) wait-postgres-ready
	$(MAKE) bootstrap-db
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) up -d
	$(MAKE) wait
	@echo ""
	@echo "SoloLakehouse is ready."
	@echo "  MinIO Console:  http://localhost:9001"
	@echo "  Trino UI:       http://localhost:8080"
	@echo "  MLflow UI:      http://localhost:5000"
	@echo "  Dagster UI:     http://localhost:3000"
	@echo "  (Optional OpenMetadata: make up-openmetadata)"
	@echo "  (Optional Superset:    make up-superset)"

up-openmetadata:
	$(DOCKER_COMPOSE) $(COMPOSE_OM) --profile openmetadata up -d postgres minio
	$(MAKE) wait-postgres-ready
	$(MAKE) bootstrap-db
	$(DOCKER_COMPOSE) $(COMPOSE_OM) --profile openmetadata up -d
	@echo "OpenMetadata UI: http://localhost:8585 (add Trino service in UI; host trino, port 8080)"

up-superset:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) up -d postgres
	$(MAKE) bootstrap-db EXTRA_POSTGRES_DATABASES=$(SUPERSET_DB_NAME)
	$(DOCKER_COMPOSE) $(COMPOSE_SUPERSET) --profile superset up -d --build
	$(MAKE) wait VERIFY_ENV="SUPERSET_CHECK=1 SUPERSET_DB_NAME=$(SUPERSET_DB_NAME)"
	@echo "Superset UI: http://localhost:8088 (login admin/admin; add Trino host trino, port 8080)"

bootstrap-db:
	EXTRA_POSTGRES_DATABASES="$(EXTRA_POSTGRES_DATABASES)" $(PYTHON) scripts/bootstrap-postgres.py

reset-mlflow-db:
	@echo "Resetting MLflow metadata database (mlflow)..."
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) stop mlflow
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) exec -T postgres sh -c "psql -U \"$$POSTGRES_USER\" -d postgres -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'mlflow' AND pid <> pg_backend_pid();\""
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) exec -T postgres sh -c "psql -U \"$$POSTGRES_USER\" -d postgres -c \"DROP DATABASE IF EXISTS mlflow;\""
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) exec -T postgres sh -c "psql -U \"$$POSTGRES_USER\" -d postgres -c \"CREATE DATABASE mlflow;\""
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) up -d mlflow
	@echo "MLflow metadata database reset complete."

down:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) down

clean:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) down -v

pipeline:
	@if [ "$(PIPELINE_MODE)" = "v1" ] || [ "$(PIPELINE_MODE)" = "legacy" ]; then \
		echo "Running legacy v1-style pipeline..."; \
		$(PYTHON) scripts/run-pipeline.py $(ARGS); \
	else \
		echo "Running v2 Dagster pipeline..."; \
		$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) exec dagster-webserver dagster job execute -w /app/dagster/workspace.yaml -j $(DAGSTER_JOB); \
	fi

pipeline-legacy:
	$(PYTHON) scripts/run-pipeline.py

pipeline-v1:
	$(MAKE) pipeline PIPELINE_MODE=v1 ARGS="$(ARGS)"

pipeline-dagster:
	$(MAKE) pipeline PIPELINE_MODE=v2 DAGSTER_JOB="$(DAGSTER_JOB)"

verify:
	$(PYTHON) scripts/verify-setup.py

verify-openmetadata:
	OPENMETADATA_CHECK=1 $(PYTHON) scripts/verify-setup.py

verify-superset:
	SUPERSET_CHECK=1 SUPERSET_DB_NAME="$(SUPERSET_DB_NAME)" $(PYTHON) scripts/verify-setup.py

test:
	$(PYTHON) -m pytest tests/ -v --tb=short --ignore=tests/integration

test-cov:
	$(PYTHON) -m pytest tests/ -v --tb=short --ignore=tests/integration --cov=ingestion --cov=transformations --cov=ml --cov-report=term-missing --cov-fail-under=70

test-cov-html:
	$(PYTHON) -m pytest tests/ -v --tb=short --ignore=tests/integration --cov=ingestion --cov=transformations --cov=ml --cov-report=term-missing --cov-report=html --cov-fail-under=70

test-integration:
	$(PYTHON) -m pytest tests/integration/ -v --tb=short -m integration

release-check:
	$(MAKE) verify
	$(MAKE) test
	$(MAKE) test-integration

lint:
	$(PYTHON) -m ruff check .

# Requires Dagster on PYTHONPATH (same as CI): pip install -r requirements.txt -r requirements-dagster.txt
typecheck:
	$(PYTHON) -m mypy ingestion/ transformations/ ml/ scripts/ dagster/

dagster-install:
	$(PYTHON) -m pip install -r requirements-dagster.txt

dagster-ui:
	$(PYTHON) -m webbrowser http://localhost:3000

setup:
	@echo "[1/4] Checking Docker daemon..."
	@docker info >/dev/null 2>&1 || (echo "Docker is not running. Please start Docker and retry." && exit 1)
	@echo "[2/4] Ensuring .env exists..."
	@test -f .env || cp .env.example .env
	@echo "[3/4] Pulling container images..."
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) pull
	@echo "[4/4] Starting services, bootstrapping databases, and waiting for health checks..."
	$(MAKE) up

wait:
	@echo "Waiting for services to become ready (timeout: 5 minutes)..."
	@start=$$(date +%s); \
	while true; do \
		if $(VERIFY_ENV) $(PYTHON) scripts/verify-setup.py >/dev/null 2>&1; then \
			echo ""; \
			echo "All services are healthy."; \
			exit 0; \
		fi; \
		now=$$(date +%s); \
		if [ $$((now - start)) -ge 300 ]; then \
			echo ""; \
			echo "Timed out after 5 minutes. Last verify output:"; \
			$(VERIFY_ENV) $(PYTHON) scripts/verify-setup.py || true; \
			exit 1; \
		fi; \
		printf "."; \
		sleep 10; \
	done
