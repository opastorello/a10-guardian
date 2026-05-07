# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**A10 Guardian** — REST API + MCP Server for A10 Networks Thunder TPS DDoS mitigation devices. Manages protected zones, monitors live DDoS incidents, tracks zone-config drift, and exposes 15 MCP tools to AI agents. Two services share the same image and codebase: the FastAPI app (port 8000) and the FastMCP server (port 8001).

## Commands

```bash
# Install editable + dev deps
pip install -e .[dev]

# Run API locally (auto-reload)
uvicorn a10_guardian.main:app --reload

# Run MCP server locally
#   stdio (default — for Claude Desktop)
python src/a10_guardian/mcp_server.py
#   streamable-http (for n8n / Claude Code remote)
MCP_TRANSPORT=streamable-http MCP_PORT=8001 python src/a10_guardian/mcp_server.py

# Lint / format
ruff check .
ruff format .

# Tests
pytest                                    # all
pytest tests/test_client.py               # one file
pytest tests/test_client.py::test_name    # one test
pytest --cov                              # with coverage (config in pyproject.toml)

# Docker (API + MCP from same image)
docker compose up --build -d
```

## Architecture

```
src/a10_guardian/
├── main.py                  # FastAPI app, lifespan, 3 background monitors, CORS, rate-limit, /health
├── mcp_server.py            # FastMCP server, 15 tools, lazy-loading Container, Bearer auth middleware
├── api/v1/
│   ├── api.py               # router aggregation
│   └── endpoints/
│       ├── system.py        # GET /system/{info,devices,license}
│       ├── mitigation.py    # zone CRUD + /under-attack/{ip} + /zones/{name}/ip/{ip} (check/add/remove)
│       ├── templates.py     # /templates list/get/create/update/delete/validate/export/import
│       └── attacks.py       # /attacks/ongoing, /attacks/incident/{id}/{stats,details}
├── core/
│   ├── config.py            # pydantic-settings; reads .env. Drives feature toggles via NOTIFY_* flags
│   ├── client.py            # A10Client: session/CSRF/retry, auto re-auth on 403
│   ├── dependencies.py      # require_scope() factory + per-IP brute-force limiter; service DI factories
│   ├── exceptions.py        # RFC 7231 ProblemDetails handlers + Template* custom exceptions
│   ├── logging.py           # Loguru setup with audit-file rotation
│   └── limiter.py           # SlowAPI instance (default 60/minute)
├── services/                # All business logic. Endpoints are thin wrappers.
│   ├── auth_service.py      # A10 form-login, CSRF extraction, session JSON cache
│   ├── system_service.py    # info / devices / license
│   ├── mitigation_service.py # ensure_mitigation (idempotent create-or-resync), zone CRUD
│   ├── template_service.py  # template file I/O + A10 validation (profiles/policies/device groups)
│   ├── attack_service.py    # ongoing incidents, stats, details, attack notifications
│   ├── zone_change_service.py # diffs zone snapshots to detect external create/modify/delete
│   └── notification_service.py # webhook (Discord/Slack/n8n) + Telegram fan-out, gated by NOTIFY_*
└── schemas/                 # Pydantic v2 — system, mitigation, template, attack, common
```

### Key Patterns

- **Service layer is canonical.** All business logic lives in `services/`. Endpoints in `api/v1/endpoints/` resolve services via DI factories in `core/dependencies.py`. MCP tools resolve services via the lazy `Container` class in `mcp_server.py`. When adding a feature, write the service first; the endpoint and MCP tool are wrappers.
- **A10Client** (`core/client.py`): handles session persistence (`config/session/session_cache.json`), automatic re-auth on 403, CSRF token injection for POST/PUT/DELETE/PATCH, retry with exponential backoff on 5xx.
- **Auth (REST):** `x-api-token` header, validated by `require_scope(*scopes)` in `core/dependencies.py`. Three token types: `API_SECRET_TOKEN` (full access), `MCP_SECRET_TOKEN` (full access, dedicated), and `API_TOKENS` (JSON dict mapping token → scope list). Scopes: `system:read`, `mitigation:read`, `mitigation:write`, `templates:read`, `templates:write`, `attacks:read`. Failed attempts are rate-limited per-IP (10 / 60s) with an in-memory counter — separate from the global SlowAPI limiter.
- **Auth (MCP HTTP):** `Authorization: Bearer <MCP_SECRET_TOKEN>` enforced by `BearerTokenMiddleware` (Starlette) passed to `mcp.run(middleware=...)`. The `/` landing route is unauthenticated; `/mcp` requires the token.
- **Templates replaced the old `DEFAULT_ZONE_PAYLOAD`.** Zones are created from JSON templates in `config/zone_templates/` (gitignored). On startup, the lifespan logs a warning if no templates exist; mitigation endpoints will fail until at least one template is configured. Bootstrap with `POST /api/v1/templates/import/{ip}?name=default` from an existing A10 zone, or `POST /api/v1/templates/{name}` with a JSON body. There is no longer a `core/constants.py`.
- **Background monitors** (started in `main.py` lifespan, each toggled by an env flag):
  - `monitor_a10_health` — gated by `NOTIFY_SYSTEM_HEALTH`, 60s fixed.
  - `monitor_ddos_attacks` — gated by `NOTIFY_ATTACK_DETECTED` OR `NOTIFY_ATTACK_MITIGATED`, interval `ATTACK_MONITORING_INTERVAL` (clamped 10–300s). Notifies on new incidents and on disappearance (mitigated). Optional 15-min "ongoing" repeats via `NOTIFY_ATTACK_ONGOING`.
  - `monitor_zone_changes` — gated by any `NOTIFY_ZONE_*`, interval `ZONE_MONITORING_INTERVAL`. Snapshots zones and diffs each tick to detect out-of-band create/modify/delete.
  - All three are independent asyncio tasks; cancelling one does not affect the others.
- **MCP tools (15)** in `mcp_server.py`: `get_system_health`, `get_system_devices`, `get_system_license`, `list_ongoing_attacks`, `list_active_mitigations`, `mitigate_ip`, `get_zone_status`, `remove_mitigation`, `zone_has_ip`, `add_ip_to_zone`, `remove_ip_from_zone`, `get_zone_template`, `set_zone_template`, `list_zone_templates`, `import_zone_template`. Template-name params are validated against `^[a-zA-Z0-9_-]{1,64}$` to block path traversal. Loguru is reconfigured to stderr-only because stdio transport uses stdout for JSON-RPC.
- **Multi-IP zone mutations** (`add_ip_to_zone`/`remove_ip_from_zone` in `mitigation_service.py`) are guarded by a process-local `threading.Lock` per `zone_name` (module-level `_ZONE_LOCKS` dict). Inside the lock the service does GET → modify → POST → GET-verify; if the post-write read shows the change didn't persist (A10 rejection or external concurrent edit), it raises 409. The lock does **not** cover multi-replica deploys — for that, swap in a distributed lock (Redis SET NX EX keyed on `zone_name`).
- **Notifications** are fan-out: `NotificationService.send_notification()` dispatches to webhook URL(s) (comma-separated `WEBHOOK_URL` supported) and Telegram if configured. Each event type has its own `NOTIFY_*` flag — toggling is per-event, not global.
- **Docs gating:** `/docs`, `/redoc`, `/openapi.json` are served only when `DOCS_ENABLED=True` (auto-true in `ENVIRONMENT=development`, auto-false in production). Override with the explicit env var.
- **CORS** is deny-by-default (empty `CORS_ORIGINS` blocks all cross-origin). `allow_credentials=False` because auth is via header, not cookies.

## Configuration

All settings live in `core/config.py` (pydantic-settings, `.env`). Required: `A10_USERNAME`, `A10_PASSWORD`, `API_SECRET_TOKEN`, `MCP_SECRET_TOKEN`. `A10_BASE_URL` is auto-built from `A10_HOST`/`A10_PORT` if not set. See `.env.example` for the full list.

## Code Style

- Python 3.10+, line length 120
- Ruff: `E, F, I, B, UP` enabled; `B008` ignored (FastAPI Depends pattern)
- Pydantic v2 throughout
- Errors return RFC 7231 ProblemDetails via handlers in `core/exceptions.py`
- Tests use `asyncio_mode = "auto"`; `pythonpath = ["src"]` is set in `pyproject.toml` so imports work without installing
