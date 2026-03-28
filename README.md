# FastAPI + PostgreSQL Template

Production-ready FastAPI template with vertical slice architecture, optimized for AI-assisted development.

**Zero config • Type-safe • AI-coding-optimized**

## Quick Start

```bash
# 1. Use this template (GitHub) or clone
git clone <your-repo>
cd <your-project>

# 2. Install dependencies
uv sync

# 3. Start services
docker-compose up -d

# 4. Run migrations
uv run alembic upgrade head

# 5. Start development
uv run uvicorn app.main:app --reload --port 8123
```

Visit `http://localhost:8123/docs` for Swagger UI.

## What's Inside

**Core Infrastructure**

- FastAPI with async/await
- PostgreSQL (Docker/Supabase/Neon/Railway)
- SQLAlchemy + Alembic migrations
- Pydantic settings with .env support

**Developer Experience**

- Strict type checking (MyPy + Pyright)
- Ruff linting & formatting
- Structured logging with request correlation
- Health check endpoints
- Docker multi-stage builds

**AI Optimization**

- Grep-able event logging
- Consistent naming patterns
- Shared utilities (pagination, timestamps)
- Self-correcting feedback loops

## Project Structure

```
app/
├── core/           # Infrastructure (config, database, logging, middleware)
├── shared/         # Cross-feature utilities (pagination, timestamps)
├── examples/       # Example feature slice (delete in your project)
└── main.py         # FastAPI application
```

## Customization

1. Update `name` in `pyproject.toml`
2. Update `APP_NAME` in `.env.example`
3. Copy `.env.example` to `.env`
4. Update database name/credentials
5. Delete `app/examples/` (demo feature)
6. Build your first feature slice

## Database Providers

Works with any PostgreSQL provider:

```bash
# Docker (default)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/mydb

# Supabase
DATABASE_URL=postgresql+asyncpg://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres

# Neon
DATABASE_URL=postgresql+asyncpg://[USER]:[PASSWORD]@[HOST].neon.tech/[DB]?sslmode=require

# Railway
DATABASE_URL=postgresql+asyncpg://postgres:[PASSWORD]@[HOST].railway.app:[PORT]/railway
```

## Commands

```bash
# Development
uv run uvicorn app.main:app --reload --port 8123

# Testing
uv run pytest -v                    # All tests
uv run pytest -v -m integration     # Integration tests only

# Type checking
uv run mypy app/
uv run pyright app/

# Linting
uv run ruff check .
uv run ruff format .

# Database
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
uv run alembic downgrade -1

# Docker
docker-compose up -d                # Start services
docker-compose logs -f app          # View logs
docker-compose down                 # Stop services
```

## Slash Commands

Built-in Claude Code commands:

- `/commit` - Create atomic commits with proper messages
- `/validate` - Run full validation suite (tests, types, linting, docker)
- `/check-ignore-comments` - Analyze type suppressions

## Features

- Type safety: Strict mode, zero suppressions
- Testing: 34 tests, <0.3s execution
- Logging: JSON structured, request correlation
- CORS: Configured for local development
- Migrations: Alembic with async support
- Health checks: `/health`, `/health/db`, `/health/ready`
- Docker: Multi-stage builds, hot reload
- Pagination: Shared utilities, consistent patterns
- Timestamps: Automatic tracking on all models

## Architecture Principles

**Vertical Slice**

- Features own their database models, logic, and routes
- Core infrastructure (config, database, logging) is shared
- Shared utilities extracted when used by 3+ features

**AI-Friendly**

- Grep-able structured logging: `logger.info("feature.action.status")`
- Type hints everywhere: AI understands contracts
- Consistent patterns: Predictable code generation
- Fast feedback: Linting/typing catches errors immediately

## Tech Stack

**Backend**

- Python 3.12+
- FastAPI 0.120+
- SQLAlchemy 2.0+ (async)
- Pydantic 2.0+

**Database**

- PostgreSQL 18 (any provider)
- Alembic migrations
- asyncpg driver

**Dev Tools**

- uv (package manager)
- Ruff (linting/formatting)
- MyPy + Pyright (type checking)
- pytest (testing)
- Docker + Docker Compose

## Requirements

- Python 3.12+
- uv (or pip)
- Docker + Docker Compose
- PostgreSQL 18+ (via Docker or cloud provider)

## License

MIT
