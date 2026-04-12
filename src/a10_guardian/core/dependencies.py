import time
from collections import defaultdict
from collections.abc import Callable
from threading import Lock
from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from a10_guardian.core.client import A10Client
from a10_guardian.core.config import settings
from a10_guardian.services.attack_service import AttackService
from a10_guardian.services.mitigation_service import MitigationService
from a10_guardian.services.notification_service import NotificationService
from a10_guardian.services.system_service import SystemService
from a10_guardian.services.template_service import TemplateService

if TYPE_CHECKING:
    from a10_guardian.services.zone_change_service import ZoneChangeService

# ---------------------------------------------------------------------------
# Scopes
# ---------------------------------------------------------------------------
ALL_SCOPES: frozenset[str] = frozenset([
    "system:read",
    "mitigation:read",
    "mitigation:write",
    "templates:read",
    "templates:write",
    "attacks:read",
])

# ---------------------------------------------------------------------------
# Token header — shows Authorize button in Swagger UI
# ---------------------------------------------------------------------------
api_key_header = APIKeyHeader(name="x-api-token", auto_error=True)

# ---------------------------------------------------------------------------
# In-memory rate limiter — max 10 failed auth attempts per IP per 60 s
# ---------------------------------------------------------------------------
_auth_failures: dict[str, list[float]] = defaultdict(list)
_auth_lock = Lock()
_AUTH_MAX_FAILURES = 10
_AUTH_WINDOW_SECONDS = 60


def _check_rate_limit(client_ip: str) -> None:
    """Raise 429 if the IP exceeded the failure threshold. Must be called inside _auth_lock."""
    now = time.monotonic()
    _auth_failures[client_ip] = [t for t in _auth_failures[client_ip] if now - t < _AUTH_WINDOW_SECONDS]
    if len(_auth_failures[client_ip]) >= _AUTH_MAX_FAILURES:
        raise HTTPException(status_code=429, detail="Too many failed authentication attempts. Try again later.")


def _record_failure(client_ip: str) -> None:
    """Record a failed auth attempt. Must be called inside _auth_lock."""
    _auth_failures[client_ip].append(time.monotonic())


def _resolve_scopes(api_key: str) -> frozenset[str] | None:
    """Return the scopes granted to this token, or None if the token is invalid."""
    if api_key == settings.API_SECRET_TOKEN:
        return ALL_SCOPES                          # internal master → full access
    if api_key == settings.MCP_SECRET_TOKEN:
        return ALL_SCOPES                          # MCP server → full access, dedicated token
    token_map: dict[str, list[str]] = settings.API_TOKENS
    if api_key in token_map:
        granted = frozenset(token_map[api_key]) & ALL_SCOPES   # only recognised scopes
        return granted
    return None


def require_scope(*required_scopes: str) -> Callable:
    """
    Dependency factory — returns a FastAPI dependency that:
      1. Rate-limits failed attempts by client IP
      2. Validates the token exists (401 if not)
      3. Checks the token has ALL the required scopes (403 if not)

    Usage:
        @router.get("/zones/list", dependencies=[Depends(require_scope("mitigation:read"))])
    """
    async def _dependency(request: Request, api_key: str = Security(api_key_header)) -> str:
        client_ip = request.client.host if request.client else "unknown"

        with _auth_lock:
            _check_rate_limit(client_ip)
            token_scopes = _resolve_scopes(api_key)
            if token_scopes is None:
                _record_failure(client_ip)
                raise HTTPException(status_code=401, detail="Invalid API Token")

        missing = frozenset(required_scopes) - token_scopes
        if missing:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Token lacks: {', '.join(sorted(missing))}",
            )

        return api_key

    # Preserve a readable name for OpenAPI / debugging
    _dependency.__name__ = f"require_scope({'_'.join(required_scopes)})"
    return _dependency


# ---------------------------------------------------------------------------
# Backward-compatible alias — full access (all scopes)
# ---------------------------------------------------------------------------
verify_api_token = require_scope(*ALL_SCOPES)


def get_a10_client():
    return A10Client(settings.A10_USERNAME, settings.A10_PASSWORD)


def get_notification_service() -> NotificationService:
    return NotificationService()


def get_system_service(client: A10Client = Depends(get_a10_client)) -> SystemService:
    return SystemService(client)


def get_mitigation_service(
    client: A10Client = Depends(get_a10_client), notifier: NotificationService = Depends(get_notification_service)
) -> MitigationService:
    return MitigationService(client, notifier)


def get_template_service(
    client: A10Client = Depends(get_a10_client), notifier: NotificationService = Depends(get_notification_service)
) -> TemplateService:
    return TemplateService(client, notifier)


def get_attack_service(
    client: A10Client = Depends(get_a10_client), notifier: NotificationService = Depends(get_notification_service)
) -> AttackService:
    return AttackService(client, notifier)


def get_zone_change_service(
    client: A10Client = Depends(get_a10_client), notifier: NotificationService = Depends(get_notification_service)
) -> "ZoneChangeService":
    from a10_guardian.services.zone_change_service import ZoneChangeService

    return ZoneChangeService(client, notifier)
