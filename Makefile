.PHONY: help install build test clean test-backend test-frontend

help:
	@echo "Commands:"
	@echo "  install       : Install backend and frontend dependencies (for local testing/linting mainly)"
	@echo "  build         : Build frontend assets (usually run via Docker)"
	@echo "  test          : Run backend and frontend tests"
	@echo "  test-backend  : Run backend tests (requires local venv or Docker exec)"
	@echo "  test-frontend : Run frontend tests (requires local node_modules or Docker exec)"
	@echo "  clean         : Remove generated files (build artifacts, pycache, etc.)"

# Variables
PYTHON = python3
PIP = $(PYTHON) -m pip
NPM = npm
VENV_DIR = backend/.venv
ACTIVATE = source $(VENV_DIR)/bin/activate || . $(VENV_DIR)/Scripts/activate

# Default target
all: install

install:
	@echo "Installing backend dependencies locally (optional)..."
	$(PYTHON) -m venv $(VENV_DIR)
	$(ACTIVATE) && $(PIP) install --upgrade pip && $(PIP) install -r backend/requirements.txt
	@echo "Installing frontend dependencies locally (optional)..."
	cd frontend && $(NPM) install

build:
	@echo "Building frontend assets..."
	cd frontend && $(NPM) run build

test-backend:
	@echo "Running backend tests (locally)..."
	$(ACTIVATE) && pytest backend/tests
	@echo "Note: Consider running tests inside the Docker container for consistency."

test-frontend:
	@echo "Running frontend tests (locally)..."
	cd frontend && $(NPM) run test
	@echo "Note: Consider running tests inside the Docker container for consistency."

test: test-backend test-frontend

clean:
	@echo "Cleaning up..."
	rm -rf backend/$(VENV_DIR) backend/.pytest_cache backend/**/__pycache__ backend/**/*.pyc
	rm -rf frontend/node_modules frontend/dist
	find . -name '__pycache__' -type d -exec rm -rf {} +
	find . -name '*.pyc' -delete
	find . -name '.DS_Store' -delete
	@echo "Docker images/volumes are not removed by this command."

# Removed the complex 'dev' target, use 'docker-compose up' instead.
# Example Docker Compose commands:
#   docker-compose up --build
#   docker-compose down
#   docker-compose exec backend pytest
#   docker-compose exec frontend npm run test 