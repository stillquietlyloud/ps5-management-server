# Contributing to PS5 Management Server

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Code of Conduct

By participating, you agree to abide by our Code of Conduct. Please be respectful and constructive.

## How to Contribute

### Reporting Bugs

1. Check if the issue already exists in [Issues](https://github.com/yourusername/ps5-management-server/issues)
2. Create a new issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python version, Docker version)
   - Screenshots if applicable

### Suggesting Features

1. Check existing issues and discussions
2. Create a feature request issue with:
   - Clear use case
   - Proposed solution
   - Any alternatives considered

### Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Make your changes
4. Run tests: `make test`
5. Run linting: `make lint`
6. Commit with clear messages
7. Push to your fork
8. Create a Pull Request

## Development Setup

### Prerequisites

- Python 3.10+
- Docker & Docker Compose (optional)
- Git

### Local Development

```bash
# Clone your fork
git clone https://github.com/yourusername/ps5-management-server.git
cd ps5-management-server

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# Install dependencies
make install

# Copy environment file
cp .env.example .env
# Edit .env with your settings

# Run development server
make dev
```

### Using Docker

```bash
# Build and start all services
make build
make up

# View logs
make logs

# Stop services
make down
```

## Code Style

- **Formatter:** Black (line length 120)
- **Import sorting:** isort (Black profile)
- **Linting:** flake8
- **Type hints:** Encouraged for new code

Run all checks:
```bash
make format  # Auto-format
make lint    # Check style
```

## Testing

```bash
# Run all tests
make test

# Run with coverage
pytest tests/ -v --cov=app --cov-report=html
```

## Project Structure

```
ps5_management_server/
├── app/
│   ├── modules/        # Feature modules (1 per file)
│   ├── api/            # REST API endpoints
│   ├── models/         # Database models
│   ├── templates/      # Jinja2 templates
│   └── static/         # CSS/JS assets
├── tests/              # Test files
├── migrations/         # Alembic migrations
├── data/               # Runtime data (gitignored)
├── logs/               # Log files (gitignored)
├── .github/            # CI/CD workflows
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── .env.example
├── Makefile
└── README.md
```

## Module Development

Each module in `app/modules/` follows the `BaseModule` interface:

```python
class MyModule(BaseModule):
    @property
    def info(self) -> ModuleInfo:
        return ModuleInfo(
            name="my_module",
            version="1.0.0",
            description="Module description",
            dependencies=["ftp"],  # Other module names
        )
    
    async def initialize(self) -> bool:
        # Setup code
        return True
    
    async def shutdown(self) -> bool:
        # Cleanup code
        return True
```

Register in `app/modules/__init__.py`:
```python
MODULE_REGISTRY["my_module"] = MyModule
MODULE_DEPENDENCIES["my_module"] = ["ftp"]
```

## Commit Messages

Follow conventional commits:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style (formatting, etc.)
- `refactor:` Code refactoring
- `test:` Adding tests
- `chore:` Maintenance tasks

Example: `feat(library): add game filtering by region`

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Questions?

Open a [Discussion](https://github.com/yourusername/ps5-management-server/discussions) or create an issue.