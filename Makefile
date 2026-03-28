.PHONY: up down clean pipeline pipeline-legacy pipeline-v1 pipeline-dagster verify test test-cov test-cov-html test-integration lint typecheck setup wait dagster-install dagster-ui

COMPOSE_FILE := docker/docker-compose.yml
PYTHON := python3
PIPELINE_MODE ?= v2
ARGS ?=
DAGSTER_JOB ?= full_pipeline_job

up:
	docker compose -f $(COMPOSE_FILE) up -d
	$(MAKE) wait
	@echo ""
	@echo "SoloLakehouse is ready."
	@echo "  MinIO Console:  http://localhost:9001"
	@echo "  Trino UI:       http://localhost:8080"
	@echo "  MLflow UI:      http://localhost:5000"
	@echo "  Dagster UI:     http://localhost:3000"

down:
	docker compose -f $(COMPOSE_FILE) down

clean:
	docker compose -f $(COMPOSE_FILE) down -v

pipeline:
	@if [ "$(PIPELINE_MODE)" = "v1" ] || [ "$(PIPELINE_MODE)" = "legacy" ]; then \
		echo "Running legacy v1-style pipeline..."; \
		$(PYTHON) scripts/run-pipeline.py $(ARGS); \
	else \
		echo "Running v2 Dagster pipeline..."; \
		docker compose -f $(COMPOSE_FILE) exec dagster-webserver dagster job execute -w /app/dagster/workspace.yaml -j $(DAGSTER_JOB); \
	fi

pipeline-legacy:
	$(PYTHON) scripts/run-pipeline.py

pipeline-v1:
	$(MAKE) pipeline PIPELINE_MODE=v1 ARGS="$(ARGS)"

pipeline-dagster:
	$(MAKE) pipeline PIPELINE_MODE=v2 DAGSTER_JOB="$(DAGSTER_JOB)"

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

lint:
	$(PYTHON) -m ruff check .

typecheck:
	$(PYTHON) -m mypy ingestion/ transformations/ ml/ scripts/

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
	docker compose -f $(COMPOSE_FILE) pull
	@echo "[4/4] Starting services and waiting for health checks..."
	$(MAKE) up

wait:
	@echo "Waiting for services to become ready (timeout: 5 minutes)..."
	@start=$$(date +%s); \
	while true; do \
		if $(PYTHON) scripts/verify-setup.py >/dev/null 2>&1; then \
			echo ""; \
			echo "All services are healthy."; \
			exit 0; \
		fi; \
		now=$$(date +%s); \
		if [ $$((now - start)) -ge 300 ]; then \
			echo ""; \
			echo "Timed out after 5 minutes."; \
			exit 1; \
		fi; \
		printf "."; \
		sleep 10; \
	done
