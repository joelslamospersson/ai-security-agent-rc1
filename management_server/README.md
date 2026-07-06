# AI Security Management Server

Central management server for the AI Security Agent. Provides machine registry, policy management, heartbeats, notifications, Discord integration, and an internal certificate authority.

> **Status:** Active Development

---

## Installation

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Copy and customize configuration
cp .env.example .env
```

## Quick Start

```bash
# Start the server
python -m management_server

# Or with uvicorn directly
uvicorn management_server.app:create_app --factory --reload
```

## Verification

```bash
curl http://localhost:8000/
curl http://localhost:8000/health
curl http://localhost:8000/version
```

## Development

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=management_server --cov-report=term
```

### Linting and Type Checking

```bash
# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/

# Type check
mypy src/
```

## Project Layout

```
management_server/
├── pyproject.toml              # Dependencies and tool config
├── .env.example                # Configuration template
├── src/
│   └── management_server/
│       ├── __main__.py         # Entry point
│       ├── app.py              # FastAPI application factory
│       ├── version.py          # Version information
│       ├── api/                # API routes and handlers
│       ├── auth/               # Authentication (Phase 2+)
│       ├── certificates/       # Certificate authority (Phase 2+)
│       ├── database/           # Database models (Phase 2+)
│       ├── config/             # Configuration loading
│       ├── models/             # Domain models (Phase 2+)
│       ├── schemas/            # Pydantic schemas (Phase 2+)
│       ├── routing/            # Routing engine (Phase 2+)
│       ├── heartbeat/          # Heartbeat processing (Phase 2+)
│       ├── machines/           # Machine registry (Phase 2+)
│       ├── policies/           # Policy engine (Phase 2+)
│       ├── audit/              # Audit system (Phase 2+)
│       ├── notifications/      # Notification engine (Phase 2+)
│       ├── discord/            # Discord bridge (Phase 2+)
│       ├── commands/           # Remote command framework (Phase 2+)
│       ├── telemetry/          # Telemetry collection (Phase 2+)
│       └── utils/              # Shared utilities
├── tests/                      # Test suite
├── migrations/                 # Alembic migrations (Phase 2+)
└── scripts/                    # Utility scripts
```

## Configuration

Settings are loaded from `.env` or environment variables with the `MGMT_` prefix.

| Variable | Default | Description |
|----------|---------|-------------|
| `MGMT_DEBUG` | `false` | Enable debug mode |
| `MGMT_LOG_LEVEL` | `INFO` | Log level |
| `MGMT_LOG_FORMAT` | `json` | Log format (json/console) |
| `MGMT_HOST` | `0.0.0.0` | Bind address |
| `MGMT_PORT` | `8000` | Bind port |
| `MGMT_SECRET_KEY` | `change-me...` | Secret key |
