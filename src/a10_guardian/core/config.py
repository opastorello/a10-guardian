from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # A10 Connection
    A10_HOST: str = Field(default="your-a10-host.example.com", description="A10 Device IP or Hostname")
    A10_PORT: int = Field(default=17489, description="A10 Device Port")
    A10_USERNAME: str = Field(..., description="A10 Admin Username")
    A10_PASSWORD: str = Field(..., description="A10 Admin Password")

    # Derived URL (can be overridden, but usually constructed)
    A10_BASE_URL: str = Field(default="", description="Full Base URL")

    # Security
    A10_VERIFY_SSL: bool = Field(default=False, description="Verify SSL Certificates")
    API_SECRET_TOKEN: str = Field(..., description="Internal master API key — full access, all scopes")
    MCP_SECRET_TOKEN: str = Field(..., description="MCP server API key — full access, dedicated token for MCP clients")
    API_TOKENS: dict[str, list[str]] = Field(
        default_factory=dict,
        description=(
            "Additional API tokens with granular scopes. JSON in .env.\n"
            "Available scopes: system:read, mitigation:read, mitigation:write, "
            "templates:read, templates:write, attacks:read\n"
            'Example: API_TOKENS={"tok_ro": ["mitigation:read","templates:read"], '
            '"tok_mit": ["mitigation:read","mitigation:write"]}'
        ),
    )
    CORS_ORIGINS: str = Field(
        default="",
        description=(
            "Allowed CORS origins (comma-separated in .env, "
            "e.g. https://app.example.com,https://admin.example.com). "
            "Empty = deny all cross-origin requests."
        ),
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS string into a list."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # App Config
    DEBUG: bool = Field(default=False)
    DOCS_ENABLED: bool = Field(default=True, description="Expose /docs and /redoc endpoints (disable in production)")
    LOG_LEVEL: str = Field(default="INFO", description="Logging Level (DEBUG, INFO, WARNING, ERROR)")
    RATE_LIMIT_DEFAULT: str = Field(default="60/minute", description="Global Rate Limit")
    # Notifications
    WEBHOOK_ENABLED: bool = Field(default=False, description="Enable external webhook notifications")
    WEBHOOK_URL: str | None = Field(
        default=None,
        description="Webhook URL(s) for notifications. Supports single or multiple (comma-separated): "
        "https://discord1 or https://discord1,https://discord2,https://slack",
    )
    WEBHOOK_USERNAME: str = Field(default="A10 Guardian", description="Display name for webhook messages")
    WEBHOOK_FOOTER: str = Field(default="A10 Guardian API", description="Footer text for webhook messages")

    # Telegram Notifications
    TELEGRAM_BOT_TOKEN: str | None = Field(default=None, description="Telegram Bot API Token")
    TELEGRAM_CHAT_ID: str | None = Field(default=None, description="Telegram Chat ID to send notifications")

    # Notification Control (granular)
    NOTIFY_TEMPLATE_CREATE: bool = Field(default=True, description="Send notification when template is created")
    NOTIFY_TEMPLATE_UPDATE: bool = Field(default=True, description="Send notification when template is updated")
    NOTIFY_TEMPLATE_DELETE: bool = Field(default=True, description="Send notification when template is deleted")
    NOTIFY_TEMPLATE_IMPORT: bool = Field(
        default=True, description="Send notification when template is imported from A10"
    )
    NOTIFY_MITIGATION_START: bool = Field(default=True, description="Send notification when mitigation starts")
    NOTIFY_MITIGATION_STOP: bool = Field(
        default=True, description="Send notification when mitigation stops/zone removed"
    )
    NOTIFY_SYSTEM_HEALTH: bool = Field(
        default=False,
        description="Monitor A10 device health (60s interval) and notify on status changes (online/offline)",
    )

    # Attack Monitoring
    NOTIFY_ATTACK_DETECTED: bool = Field(default=True, description="Send notification when DDoS attack is detected")
    NOTIFY_ATTACK_MITIGATED: bool = Field(default=True, description="Send notification when attack is mitigated/ended")
    NOTIFY_ATTACK_ONGOING: bool = Field(
        default=False, description="Send periodic notifications for long-running attacks (every 15min)"
    )
    ATTACK_MONITORING_INTERVAL: int = Field(
        default=30, description="How often to check for new attacks (in seconds, min: 10, max: 300)"
    )

    # Zone Change Monitoring
    NOTIFY_ZONE_CREATED: bool = Field(default=True, description="Send notification when zone is created outside API")
    NOTIFY_ZONE_MODIFIED: bool = Field(
        default=True, description="Send notification when zone configuration is modified outside API"
    )
    NOTIFY_ZONE_DELETED: bool = Field(default=True, description="Send notification when zone is deleted outside API")
    ZONE_MONITORING_INTERVAL: int = Field(
        default=30, description="How often to check for zone changes (in seconds, min: 10, max: 300)"
    )

    # Template Configuration
    TEMPLATE_DIR: str = Field(default="config/zone_templates", description="Zone template storage directory")

    # Session
    SESSION_CACHE_TTL: int = 3600
    SESSION_CACHE_FILE: str = "config/session/session_cache.json"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.A10_BASE_URL:
            protocol = "https"
            self.A10_BASE_URL = f"{protocol}://{self.A10_HOST}:{self.A10_PORT}"


settings = Settings()
