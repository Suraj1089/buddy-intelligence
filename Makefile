# ==============================================================================
# Buddy Intelligence - Makefile
# ==============================================================================
# This Makefile provides convenient commands for development, testing, and
# deployment of the FastAPI backend application.
#
# Usage: make <command>
# Run 'make help' to see all available commands
# ==============================================================================

# ------------------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------------------

# Python and virtual environment
PYTHON := python3
UV := uv
BACKEND_DIR := backend

# Docker configuration
DOCKER_COMPOSE := docker-compose

# Application settings
APP_MODULE := app.main:app
CELERY_APP := app.core.celery_app

# Default shell
SHELL := /bin/bash

# ------------------------------------------------------------------------------
# HELP
# ------------------------------------------------------------------------------

.PHONY: help
help: ## Show this help message
	@echo "Buddy Intelligence - Development Commands"
	@echo ""
	@echo "Usage: make <command>"
	@echo ""
	@echo "Commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ------------------------------------------------------------------------------
# INSTALLATION & SETUP
# ------------------------------------------------------------------------------

.PHONY: install
install: ## Install all dependencies using uv
	cd $(BACKEND_DIR) && $(UV) sync

.PHONY: install-dev
install-dev: ## Install development dependencies
	cd $(BACKEND_DIR) && $(UV) sync --all-extras

.PHONY: upgrade
upgrade: ## Upgrade all dependencies to latest versions
	cd $(BACKEND_DIR) && $(UV) sync --upgrade

# ------------------------------------------------------------------------------
# VIRTUAL ENVIRONMENT
# ------------------------------------------------------------------------------

.PHONY: venv
venv: ## Create virtual environment using uv
	cd $(BACKEND_DIR) && $(UV) venv

.PHONY: venv-activate
venv-activate: ## Show command to activate virtual environment
	@echo "Run this command to activate the virtual environment:"
	@echo "  source $(BACKEND_DIR)/.venv/bin/activate"

.PHONY: venv-deactivate
venv-deactivate: ## Show command to deactivate virtual environment
	@echo "Run this command to deactivate:"
	@echo "  deactivate"

.PHONY: venv-clean
venv-clean: ## Remove virtual environment
	rm -rf $(BACKEND_DIR)/.venv
	@echo "Virtual environment removed"

.PHONY: venv-info
venv-info: ## Show virtual environment info
	@echo "Virtual Environment Location: $(BACKEND_DIR)/.venv"
	@echo ""
	@echo "uv automatically manages the virtual environment."
	@echo "All 'make' commands use 'uv run' which activates the venv automatically."
	@echo ""
	@echo "For manual activation, run:"
	@echo "  source $(BACKEND_DIR)/.venv/bin/activate"

# ------------------------------------------------------------------------------
# DEVELOPMENT SERVER
# ------------------------------------------------------------------------------

.PHONY: dev
dev: ## Start FastAPI development server with hot reload
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run fastapi dev app/main.py

.PHONY: run
run: ## Start FastAPI production server
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run uvicorn $(APP_MODULE) --host 0.0.0.0 --port 8000

.PHONY: dev-reload
dev-reload: ## Start development server with more verbose logging
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run uvicorn $(APP_MODULE) --reload --log-level debug

.PHONY: shell
shell: ## Start interactive IPython shell with app context
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run python interactive_shell.py


# ------------------------------------------------------------------------------
# CELERY (BACKGROUND TASKS)
# ------------------------------------------------------------------------------

.PHONY: celery
celery: ## Start Celery worker for background tasks
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run celery -A $(CELERY_APP) worker -l info

.PHONY: celery-beat
celery-beat: ## Start Celery beat scheduler for periodic tasks
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run celery -A $(CELERY_APP) beat -l info

.PHONY: celery-flower
celery-flower: ## Start Flower (Celery monitoring dashboard) on port 5555
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run celery -A $(CELERY_APP) flower --port=5555

.PHONY: celery-all
celery-all: ## Start both Celery worker and beat in background (use with caution)
	@echo "Starting Celery worker and beat..."
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run celery -A $(CELERY_APP) worker -l info --detach
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run celery -A $(CELERY_APP) beat -l info --detach
	@echo "Celery services started in background"

# ------------------------------------------------------------------------------
# REDIS
# ------------------------------------------------------------------------------

.PHONY: redis
redis: ## Start Redis server (requires redis-server installed)
	redis-server

.PHONY: redis-cli
redis-cli: ## Open Redis CLI for debugging
	redis-cli

.PHONY: redis-flush
redis-flush: ## Flush all Redis data (WARNING: deletes all data)
	redis-cli FLUSHALL

# ------------------------------------------------------------------------------
# DATABASE
# ------------------------------------------------------------------------------

.PHONY: db-upgrade
db-upgrade: ## Run database migrations (upgrade to latest)
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run alembic upgrade head

.PHONY: db-downgrade
db-downgrade: ## Rollback last database migration
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run alembic downgrade -1

.PHONY: db-revision
db-revision: ## Create a new migration (usage: make db-revision msg="description")
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run alembic revision --autogenerate -m "$(msg)"

.PHONY: db-history
db-history: ## Show migration history
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run alembic history

.PHONY: db-current
db-current: ## Show current migration version
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run alembic current

.PHONY: db-init
db-init: ## Initialize database with initial data
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run python -m app.initial_data

.PHONY: db-create
db-create: ## Create new database (requires postgres user access)
	@echo "Creating database 'buddy_app'..."
	psql -U surajpisal -p 6432 -c "CREATE DATABASE buddy_app;" || echo "Database may already exist"
	@echo "Database created!"

.PHONY: db-drop
db-drop: ## Drop database (WARNING: deletes all data)
	@echo "WARNING: This will delete all data!"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] && \
		psql -U surajpisal -p 6432 -c "DROP DATABASE IF EXISTS buddy_app;" || echo "Cancelled"

.PHONY: db-reset
db-reset: ## Reset database (drop, create, migrate, seed)
	@echo "Resetting database..."
	psql -U surajpisal -p 6432 -c "DROP DATABASE IF EXISTS buddy_app;"
	psql -U surajpisal -p 6432 -c "CREATE DATABASE buddy_app;"
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run alembic upgrade head
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run python -m app.initial_data
	@echo "Database reset complete!"

.PHONY: db-migrate
db-migrate: db-upgrade ## Alias for db-upgrade (run migrations)

.PHONY: db-seed
db-seed: ## Seed database with sample data
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run python scripts/seed_data.py

.PHONY: db-setup
db-setup: db-create db-upgrade db-init ## Full database setup: create, migrate, init
	@echo "Database setup complete!"

.PHONY: db-shell
db-shell: ## Open psql shell to the database
	psql -U surajpisal -d buddy_app -p 6432

# ------------------------------------------------------------------------------
# TESTING
# ------------------------------------------------------------------------------

.PHONY: test
test: ## Run all tests
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run pytest -v

.PHONY: test-cov
test-cov: ## Run tests with coverage report
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run pytest --cov=app --cov-report=term-missing --cov-report=html

.PHONY: test-auth
test-auth: ## Run only authentication tests
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run pytest tests/test_auth.py -v

.PHONY: test-bookings
test-bookings: ## Run only booking tests
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run pytest tests/test_bookings.py -v

.PHONY: test-assignments
test-assignments: ## Run only assignment tests
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run pytest tests/test_assignments.py -v

.PHONY: test-services
test-services: ## Run only services tests
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run pytest tests/test_services.py -v

.PHONY: test-providers
test-providers: ## Run only provider tests
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run pytest tests/test_providers.py -v

.PHONY: test-fast
test-fast: ## Run tests without slow tests
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run pytest -v -m "not slow"

.PHONY: test-watch
test-watch: ## Run tests in watch mode (requires pytest-watch)
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run ptw

# ------------------------------------------------------------------------------
# LINTING & FORMATTING
# ------------------------------------------------------------------------------

.PHONY: lint
lint: ## Run linters (ruff)
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run ruff check .

.PHONY: lint-fix
lint-fix: ## Run linters and auto-fix issues
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run ruff check . --fix

.PHONY: format
format: ## Format code with ruff
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run ruff format .

.PHONY: format-check
format-check: ## Check if code is formatted
	unset POSTGRES_PORT && cd $(BACKEND_DIR) && $(UV) run ruff format . --check

.PHONY: type-check
type-check: ## Run type checking with mypy
	cd $(BACKEND_DIR) && $(UV) run mypy app

# ------------------------------------------------------------------------------
# DOCKER
# ------------------------------------------------------------------------------

.PHONY: docker-build
docker-build: ## Build Docker image
	$(DOCKER_COMPOSE) build

.PHONY: docker-up
docker-up: ## Start all Docker containers
	$(DOCKER_COMPOSE) up -d

.PHONY: docker-down
docker-down: ## Stop all Docker containers
	$(DOCKER_COMPOSE) down

.PHONY: docker-logs
docker-logs: ## View Docker container logs
	$(DOCKER_COMPOSE) logs -f

.PHONY: docker-clean
docker-clean: ## Remove all Docker containers and volumes
	$(DOCKER_COMPOSE) down -v --remove-orphans

# ------------------------------------------------------------------------------
# CLEANUP
# ------------------------------------------------------------------------------

.PHONY: clean
clean: ## Clean up generated files and caches
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	@echo "Cleanup complete!"

# ------------------------------------------------------------------------------
# DEVELOPMENT SHORTCUTS
# ------------------------------------------------------------------------------

.PHONY: setup
setup: install db-upgrade db-init ## Complete setup: install deps, run migrations, init data
	@echo "Setup complete! Run 'make dev' to start the server"

.PHONY: fresh
fresh: clean install db-upgrade db-init ## Fresh install: clean, install, migrate, init
	@echo "Fresh setup complete!"

.PHONY: all
all: lint-fix format test ## Run all checks: lint, format, test
