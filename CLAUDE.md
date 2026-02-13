# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**A10 Guardian** — REST API + MCP Server for A10 Networks Thunder TPS DDoS mitigation devices. Provides zone management, system monitoring, webhook notifications, and AI agent integration via Model Context Protocol.

## Commands

```bash
# Install (editable with dev deps)
pip install -e .[dev]

# Run API locally (auto-reload)
uvicorn a10_guardian.main:app --reload

# Run MCP server locally
python src/a10_guardian/mcp_server.py

# Lint and format
ruff check .
ruff format .

# Run all tests
pytest

# Run single test file
pytest tests/test_client.py

# Docker (API + MCP)
docker compose up --build -d
```

## Architecture

```
src/a10_guardian/
├── main.py                  # FastAPI app, middleware, startup
├── mcp_server.py            # MCP server (5 tools for AI agents)
├── api/v1/
│   ├── api.py               # V1 router aggregation
│   └── endpoints/
│       ├── system.py         # GET /api/v1/system/* (info, devices, license)
│       └── mitigation.py     # /api/v1/mitigation/* (mitigate, list, status, remove)
├── core/
│   ├── config.py             # Settings via pydantic-settings (reads .env)
│   ├── client.py             # A10Client — HTTP client with session/CSRF/retry handling
│   ├── dependencies.py       # FastAPI DI factories (verify_api_token, get_*_service)
│   ├── constants.py          # DEFAULT_ZONE_PAYLOAD (golden zone creation template)
│   ├── exceptions.py         # Global exception handlers (RFC 7231 ProblemDetails)
│   ├── logging.py            # Loguru setup with audit file rotation
│   └── limiter.py            # SlowAPI rate limiter instance
├── services/
│   ├── auth_service.py       # A10 login, CSRF extraction, session caching to JSON
│   ├── system_service.py     # System info, devices, license
│   ├── mitigation_service.py # Zone CRUD, ensure_mitigation (idempotent), zone status
│   └── notification_service.py # Webhook alerts (Slack/Discord)
└── schemas/
    ├── system.py             # SystemInfoResponse, LicenseInfo, DeviceInfo
    ├── mitigation.py         # ZoneStatusResponse, ZoneListResponse
    └── common.py             # GenericResponse
```

### Key Patterns

- **Service layer**: All business logic lives in `services/`. Endpoints are thin wrappers that call services via FastAPI dependency injection (`core/dependencies.py`).
- **A10Client** (`core/client.py`): Handles session persistence, automatic re-auth on 403, CSRF token injection for POST/PUT/DELETE/PATCH, and retry with exponential backoff for 5xx errors.
- **Auth flow**: Form-based login → CSRF token extracted from HTML → session cookies cached to `session_cache.json` → auto-renewed on expiry.
- **All endpoints require `x-api-token` header**, verified by `verify_api_token()` dependency.
- **DEFAULT_ZONE_PAYLOAD** in `constants.py` is the golden template for zone creation with 23 protection services including game-server profiles (FiveM, Minecraft, Rust, ARK, etc.).
- **MCP server** (`mcp_server.py`) uses a lazy-loading `Container` class to provide 5 tools (`get_system_health`, `list_active_mitigations`, `mitigate_ip`, `get_zone_status`, `remove_mitigation`) for AI agent integration. Supports stdio and streamable-http transports.
- **Docker Compose** runs two services sharing the same image: API (port 8000) and MCP (port 8001).

## Configuration

Required env vars (see `.env.example`): `A10_USERNAME`, `A10_PASSWORD`, `API_SECRET_TOKEN`, `A10_BASE_URL`. All settings defined in `core/config.py` using pydantic `BaseSettings`.

## Code Style

- Python 3.10+, line length 120
- Ruff linting rules: E, F, I (isort), B (bugbear), UP (pyupgrade)
- Pydantic v2 for all schemas
- Exception responses use RFC 7231 ProblemDetails format
