# PS5 Management Server - Makefile
# Usage: make <target>

.PHONY: help install dev test lint build up down logs clean

# Default target
help:
	@echo "PS5 Management Server - Available Commands:"
	@echo ""
	@echo "  make install    - Install Python dependencies"
	@echo "  make dev        - Run development server (with hot reload)"
	@echo "  make prod       - Run production server (gunicorn)"
	@echo "  make test       - Run tests"
	@echo "  make lint       - Run linting"
	@echo "  make build      - Build Docker image"
	@echo "  make up         - Start all services (Docker Compose)"
	@echo "  make down       - Stop all services (Docker Compose)"
	@echo "  make logs       - View Docker logs"
	@echo "  make clean      - Clean up generated files"
	@echo "  make db-init    - Initialize database"
	@echo "  make db-migrate - Run database migrations"
	@echo ""

# Install dependencies
install:
	pip install --upgrade pip
	pip install -r requirements.txt

# Development server with hot reload
dev:
	DEBUG=true python main.py

# Production server with gunicorn
prod:
	gunicorn -w 4 -b 0.0.0.0:8080 --worker-class eventlet "app:create_app()"

# Run tests
test:
	pytest tests/ -v --cov=app --cov-report=term-missing

# Lint code
lint:
	flake8 app/ tests/ --max-line-length=120
	black --check app/ tests/

# Format code
format:
	black app/ tests/

# Build Docker image
build:
	docker compose build

# Start all services
up:
	docker compose up -d

# Stop all services
down:
	docker compose down

# View logs
logs:
	docker compose logs -f

# Clean up
clean:
	rm -rf __pycache__ .pytest_cache .coverage htmlcov
	rm -rf *.egg-info dist build
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Initialize database
db-init:
	python -c "from app import create_app; from app.database import init_db; app = create_app(); init_db(app); print('Database initialized')"

# Run migrations
db-migrate:
	alembic upgrade head

# Create migration
db-create-migration:
	@read -p "Migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

# Install pre-commit hooks
pre-commit:
	pre-commit install

# Run pre-commit on all files
pre-commit-run:
	pre-commit run --all-files