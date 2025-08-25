# Gweta Makefile (Vercel + Milvus + OpenAI Edition)
# Common development and deployment commands for serverless architecture

.PHONY: help setup test lint format clean dev deploy

# Default target - show help
help:
	@echo "Gweta Development Commands (Serverless)"
	@echo "==========================================="
	@echo "Setup & Installation:"
	@echo "  make setup        - Initial project setup (install deps, hooks, Vercel CLI)"
	@echo "  make install      - Install/update dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make dev          - Start Vercel development server"
	@echo "  make test         - Run all tests"
	@echo "  make test-unit    - Run unit tests only"
	@echo "  make test-watch   - Run tests in watch mode"
	@echo "  make lint         - Run linters (ruff, mypy)"
	@echo "  make format       - Auto-format code (black, isort)"
	@echo "  make security     - Run security checks"
	@echo ""
	@echo "Data & AI:"
	@echo "  make crawl        - Crawl legal documents from ZimLII"
	@echo "  make parse        - Parse and chunk documents"
	@echo "  make embed        - Generate embeddings and upload to Milvus"
	@echo "  make init-milvus  - Initialize Milvus collection"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy       - Deploy to Vercel production"
	@echo "  make deploy-preview - Deploy to Vercel preview"
	@echo "  make logs         - View Vercel function logs"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean        - Remove build artifacts and caches"

# Initial setup
setup:
	@echo "🚀 Setting up Gweta serverless development environment..."
	poetry install --with dev
	poetry run pre-commit install
	@echo "📦 Installing Vercel CLI..."
	npm install -g vercel
	@echo "✅ Setup complete! Run 'make dev' to start developing."

# Install dependencies
install:
	poetry install --with dev

# Development server (Vercel)
dev:
	@echo "🚀 Starting Vercel development server..."
	vercel dev

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

# Data & AI commands
crawl:
	@echo "🕷️ Crawling legal documents from ZimLII..."
	poetry run python scripts/crawl_zimlii.py

parse:
	@echo "📝 Parsing and chunking documents..."
	poetry run python scripts/parse_docs.py

embed:
	@echo "🧠 Generating embeddings and uploading to Milvus..."
	poetry run python scripts/generate_embeddings.py

init-milvus:
	@echo "🗄️ Initializing Milvus collection..."
	poetry run python scripts/init-milvus.py

# Deployment (Vercel)
deploy:
	@echo "🚀 Deploying to Vercel production..."
	vercel --prod

deploy-preview:
	@echo "🔍 Deploying to Vercel preview..."
	vercel

logs:
	@echo "📋 Viewing Vercel function logs..."
	vercel logs --follow

health:
	@echo "Checking service health..."
	@curl -s http://localhost:3000/api/healthz || echo "API not responding (make sure 'make dev' is running)"
	@echo ""

health-check: health

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
