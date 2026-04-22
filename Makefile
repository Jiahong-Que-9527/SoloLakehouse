.PHONY: up down clean bootstrap-db reset-mlflow-db wait-postgres-ready pipeline pipeline-dagster verify test test-cov test-cov-html test-integration release-check lint typecheck setup wait dagster-install dagster-ui prepare-data-dirs purge-legacy-docker-volumes

COMPOSE_FILE := docker/docker-compose.yml
COMPOSE_STACK := -f docker/docker-compose.yml -f docker/docker-compose.openmetadata.yml -f docker/docker-compose.superset.yml
ENV_FILE ?= .env
DOCKER_COMPOSE := docker compose --env-file $(ENV_FILE)
PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
DAGSTER_JOB ?= full_pipeline_job
SUPERSET_DB_NAME ?= superset_metadata

# Runtime state (MinIO, Postgres, Dagster, OM) lives under docker/data/ (bind mounts), not Docker named volumes.
prepare-data-dirs:
	@sh scripts/prepare-docker-data-dirs.sh

# Remove old named volumes from layouts before bind mounts (run after `make down`).
purge-legacy-docker-volumes:
	@sh scripts/purge-legacy-docker-volumes.sh

# Ensure required DBs exist before MLflow and other clients start (avoids race with bootstrap-db).
wait-postgres-ready:
	@echo "Waiting for PostgreSQL to accept connections..."
	@for i in $$(seq 1 90); do \
		docker exec slh-postgres sh -c 'pg_isready -U "$$POSTGRES_USER" -d postgres' >/dev/null 2>&1 && exit 0; \
		sleep 1; \
	done; \
	echo "Postgres did not become ready in time."; exit 1

up: prepare-data-dirs
	$(DOCKER_COMPOSE) $(COMPOSE_STACK) up -d postgres minio
	$(MAKE) wait-postgres-ready
	$(MAKE) bootstrap-db
	$(DOCKER_COMPOSE) $(COMPOSE_STACK) up -d --build
	$(MAKE) wait
	@echo ""
	@echo "SoloLakehouse is ready."
	@echo "  MinIO Console:  http://localhost:9001"
	@echo "  Trino UI:       http://localhost:8080"
	@echo "  MLflow UI:      http://localhost:5000"
	@echo "  Dagster UI:     http://localhost:3000"
	@echo "  OpenMetadata:  http://localhost:8585"
	@echo "  Superset UI:   http://localhost:8088"

bootstrap-db:
	EXTRA_POSTGRES_DATABASES="$(EXTRA_POSTGRES_DATABASES)" $(PYTHON) scripts/bootstrap-postgres.py

reset-mlflow-db:
	@echo "Resetting MLflow metadata database (mlflow)..."
	$(DOCKER_COMPOSE) $(COMPOSE_STACK) stop mlflow
	$(DOCKER_COMPOSE) $(COMPOSE_STACK) exec -T postgres sh -c "psql -U \"$$POSTGRES_USER\" -d postgres -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'mlflow' AND pid <> pg_backend_pid();\""
	$(DOCKER_COMPOSE) $(COMPOSE_STACK) exec -T postgres sh -c "psql -U \"$$POSTGRES_USER\" -d postgres -c \"DROP DATABASE IF EXISTS mlflow;\""
	$(DOCKER_COMPOSE) $(COMPOSE_STACK) exec -T postgres sh -c "psql -U \"$$POSTGRES_USER\" -d postgres -c \"CREATE DATABASE mlflow;\""
	$(DOCKER_COMPOSE) $(COMPOSE_STACK) up -d mlflow
	@echo "MLflow metadata database reset complete."

down:
	$(DOCKER_COMPOSE) $(COMPOSE_STACK) down --remove-orphans

clean:
	$(DOCKER_COMPOSE) $(COMPOSE_STACK) down --remove-orphans
	rm -rf docker/data/minio docker/data/postgres docker/data/dagster docker/data/om-mysql docker/data/om-elasticsearch
	$(MAKE) prepare-data-dirs
	$(MAKE) purge-legacy-docker-volumes

pipeline:
	@echo "Running v2.5 Dagster pipeline..."
	$(DOCKER_COMPOSE) $(COMPOSE_STACK) exec dagster-webserver dagster job execute -f /app/dagster/definitions.py -j $(DAGSTER_JOB)

pipeline-dagster:
	$(MAKE) pipeline DAGSTER_JOB="$(DAGSTER_JOB)"

verify:
	$(PYTHON) scripts/verify-setup.py

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
	$(DOCKER_COMPOSE) $(COMPOSE_STACK) pull
	@echo "[4/4] Starting services, bootstrapping databases, and waiting for health checks..."
	$(MAKE) up

wait:
	@echo "Waiting for services to become ready (timeout: 5 minutes)..."
	@start=$$(date +%s); \
	while true; do \
		if SUPERSET_DB_NAME="$(SUPERSET_DB_NAME)" $(PYTHON) scripts/verify-setup.py >/dev/null 2>&1; then \
			echo ""; \
			echo "All services are healthy."; \
			exit 0; \
		fi; \
		now=$$(date +%s); \
		if [ $$((now - start)) -ge 300 ]; then \
			echo ""; \
			echo "Timed out after 5 minutes. Last verify output:"; \
			SUPERSET_DB_NAME="$(SUPERSET_DB_NAME)" $(PYTHON) scripts/verify-setup.py || true; \
			exit 1; \
		fi; \
		printf "."; \
		sleep 10; \
	done
