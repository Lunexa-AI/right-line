# RightLine Makefile
# Common development and deployment commands

.PHONY: help setup test lint format clean dev up down

# Default target - show help
help:
	@echo "RightLine Development Commands"
	@echo "=============================="
	@echo "Setup & Installation:"
	@echo "  make setup        - Initial project setup (install deps, hooks)"
	@echo "  make install      - Install/update dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make dev          - Start development environment"
	@echo "  make test         - Run all tests"
	@echo "  make test-unit    - Run unit tests only"
	@echo "  make test-watch   - Run tests in watch mode"
	@echo "  make lint         - Run linters (ruff, mypy)"
	@echo "  make format       - Auto-format code (black, isort)"
	@echo "  make security     - Run security checks"
	@echo ""
	@echo "Docker:"
	@echo "  make up           - Start all services with docker-compose"
	@echo "  make down         - Stop all services"
	@echo "  make logs         - View service logs"
	@echo "  make build        - Build docker images"
	@echo ""
	@echo "Database:"
	@echo "  make db-migrate   - Run database migrations"
	@echo "  make db-rollback  - Rollback last migration"
	@echo "  make seed-sample  - Load sample data"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy-vps   - Deploy to VPS"
	@echo "  make deploy-k8s   - Deploy to Kubernetes"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean        - Remove build artifacts and caches"

# Initial setup
setup:
	@echo "🚀 Setting up RightLine development environment..."
	poetry install --with dev
	poetry run pre-commit install
	@echo "✅ Setup complete! Run 'make dev' to start developing."

# Install dependencies
install:
	poetry install --with dev

# Development server
dev:
	poetry run uvicorn services.api.main:app --reload --host 0.0.0.0 --port 8000

# Testing
test:
	poetry run pytest tests/ -v

test-unit:
	poetry run pytest tests/unit/ -v -m unit

test-integration:
	poetry run pytest tests/integration/ -v -m integration

test-e2e:
	poetry run pytest tests/e2e/ -v -m e2e

test-watch:
	poetry run pytest-watch tests/ -v

test-coverage:
	poetry run pytest tests/ --cov=services --cov=libs --cov-report=html --cov-report=term

# Code quality
lint:
	poetry run ruff check services/ libs/ tests/
	poetry run mypy services/ libs/

format:
	poetry run black services/ libs/ tests/
	poetry run ruff check --fix services/ libs/ tests/

security:
	poetry run bandit -r services/ libs/
	poetry run safety check

security-check: security

# Docker commands
up:
	docker-compose up -d

up-dev:
	docker-compose up -d

up-staging:
	docker-compose -f docker-compose.staging.yml up -d

up-prod:
	docker-compose -f docker-compose.production.yml up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

logs-api:
	docker-compose logs -f api

build:
	docker-compose build

build-api:
	docker build -f services/api/Dockerfile -t rightline/api:dev .

build-ingestion:
	docker build -f services/ingestion/Dockerfile -t rightline/ingestion:dev .

build-retrieval:
	docker build -f services/retrieval/Dockerfile -t rightline/retrieval:dev .

build-summarizer:
	docker build -f services/summarizer/Dockerfile -t rightline/summarizer:dev .

build-prod:
	docker-compose -f docker-compose.production.yml build

health:
	@echo "Checking service health..."
	@curl -s http://localhost:8000/health || echo "API not responding"
	@echo ""

health-check: health

# Database commands
db-migrate:
	poetry run alembic upgrade head

db-rollback:
	poetry run alembic downgrade -1

db-reset:
	poetry run alembic downgrade base
	poetry run alembic upgrade head

seed-sample:
	poetry run python scripts/seed_data.py

seed-data: seed-sample

# Deployment
deploy-vps:
	@echo "Deploying to VPS..."
	./scripts/deploy_vps.sh

deploy-k8s:
	@echo "Deploying to Kubernetes..."
	kubectl apply -k infra/k8s/

deploy-cloud:
	@echo "Deploying to cloud..."
	./scripts/deploy_cloud.sh

# Monitoring
monitor:
	@echo "Opening monitoring dashboards..."
	@open http://localhost:3001  # Grafana
	@open http://localhost:9090  # Prometheus

smoke-test:
	@echo "Running smoke tests..."
	./scripts/smoke_test.sh

# Cleanup
clean:
	@echo "Cleaning up..."
	rm -rf dist/ build/ *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf reports/

# Development utilities
shell:
	poetry shell

repl:
	poetry run ipython

deps-check:
	poetry show --outdated

deps-update:
	poetry update

# Pre-commit
pre-commit:
	poetry run pre-commit run --all-files

# Documentation
docs:
	poetry run mkdocs serve

docs-build:
	poetry run mkdocs build

# Version management
version:
	@poetry version

version-patch:
	poetry version patch

version-minor:
	poetry version minor

version-major:
	poetry version major
