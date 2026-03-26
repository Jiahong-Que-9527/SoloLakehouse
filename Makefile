.PHONY: up down clean pipeline verify test test-cov test-cov-html test-integration lint typecheck setup wait

COMPOSE_FILE := docker/docker-compose.yml

up:
	docker compose -f $(COMPOSE_FILE) up -d
	@echo "MinIO API:      http://localhost:9000"
	@echo "MinIO Console:  http://localhost:9001"
	@echo "Trino UI:       http://localhost:8080"
	@echo "MLflow UI:      http://localhost:5000"
	@echo "Postgres:       localhost:5432"

down:
	docker compose -f $(COMPOSE_FILE) down

clean:
	docker compose -f $(COMPOSE_FILE) down -v

pipeline:
	python scripts/run-pipeline.py

verify:
	python scripts/verify-setup.py

test:
	pytest tests/ -v --tb=short --ignore=tests/integration

test-cov:
	pytest tests/ -v --tb=short --ignore=tests/integration --cov=ingestion --cov=transformations --cov=ml --cov-report=term-missing --cov-fail-under=70

test-cov-html:
	pytest tests/ -v --tb=short --ignore=tests/integration --cov=ingestion --cov=transformations --cov=ml --cov-report=term-missing --cov-report=html --cov-fail-under=70

test-integration:
	pytest tests/integration/ -v --tb=short -m integration

lint:
	ruff check .

typecheck:
	mypy ingestion/ transformations/ ml/ scripts/

setup:
	@docker info >/dev/null 2>&1 || (echo "Docker is not running. Please start Docker and retry." && exit 1)
	@test -f .env || cp .env.example .env
	docker compose -f $(COMPOSE_FILE) pull
	$(MAKE) up

wait:
	@echo "Waiting for services to become ready (timeout: 5 minutes)..."
	@start=$$(date +%s); \
	while true; do \
		if python scripts/verify-setup.py >/dev/null 2>&1; then \
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
