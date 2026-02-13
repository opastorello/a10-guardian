import os
import sys

from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from loguru import logger

from a10_guardian.core.client import A10Client
from a10_guardian.core.config import settings
from a10_guardian.services.mitigation_service import MitigationService
from a10_guardian.services.notification_service import NotificationService
from a10_guardian.services.system_service import SystemService
from a10_guardian.services.template_service import TemplateService

# Configure Logging for MCP (StdErr only to avoid breaking JSON-RPC on StdOut)
logger.remove()
logger.add(sys.stderr, level=os.environ.get("LOG_LEVEL", "INFO"))
logger.add(
    "logs/mcp.log",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    rotation="10 MB",
    retention="30 days",
)

# Transport config from env vars (defaults: stdio for local, http for Docker)
MCP_TRANSPORT = os.environ.get("MCP_TRANSPORT", "stdio")
MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_PORT", "8001"))

# Auth: Bearer token only for HTTP transports (stdio doesn't need auth)
auth_provider = None
if MCP_TRANSPORT != "stdio":
    auth_provider = StaticTokenVerifier(
        tokens={
            settings.API_SECRET_TOKEN: {
                "client_id": "mcp-client",
                "scopes": ["admin"],
            }
        }
    )
    logger.info("MCP HTTP auth enabled (Bearer token required)")

# Create MCP Server
mcp = FastMCP("A10 Guardian", auth=auth_provider)

# Landing page for HTTP transport (GET /)
if MCP_TRANSPORT != "stdio":
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def root(request: Request):
        return JSONResponse(
            {
                "service": "A10 Guardian MCP Server",
                "version": "1.0.0",
                "transport": MCP_TRANSPORT,
                "endpoint": "/mcp",
                "tools": [
                    "get_system_health",
                    "list_active_mitigations",
                    "mitigate_ip",
                    "get_zone_status",
                    "remove_mitigation",
                    "get_zone_template",
                    "set_zone_template",
                    "list_zone_templates",
                    "import_zone_template",
                ],
            }
        )

    mcp._additional_http_routes.append(Route("/", root))


# Lazy Loading Container
class Container:
    _client: A10Client | None = None
    _system_service: SystemService | None = None
    _mitigation_service: MitigationService | None = None
    _notification_service: NotificationService | None = None
    _template_service: TemplateService | None = None

    @classmethod
    def get_client(cls) -> A10Client:
        if not cls._client:
            if not settings.A10_USERNAME or not settings.A10_PASSWORD:
                raise ValueError("A10 Credentials not configured.")
            cls._client = A10Client(settings.A10_USERNAME, settings.A10_PASSWORD)
        return cls._client

    @classmethod
    def get_system_service(cls) -> SystemService:
        if not cls._system_service:
            cls._system_service = SystemService(cls.get_client())
        return cls._system_service

    @classmethod
    def get_mitigation_service(cls) -> MitigationService:
        if not cls._mitigation_service:
            cls._mitigation_service = MitigationService(cls.get_client(), cls.get_notification_service())
        return cls._mitigation_service

    @classmethod
    def get_notification_service(cls) -> NotificationService:
        if not cls._notification_service:
            cls._notification_service = NotificationService()
        return cls._notification_service

    @classmethod
    def get_template_service(cls) -> TemplateService:
        if not cls._template_service:
            cls._template_service = TemplateService(cls.get_client(), cls.get_notification_service())
        return cls._template_service


@mcp.tool()
def get_system_health() -> str:
    """Returns the health status and basic info of the A10 device."""
    try:
        service = Container.get_system_service()
        info = service.get_info()
        return (
            f"System Online\n"
            f"Hostname: {info.get('hostname')}\n"
            f"Version: {info.get('agalaxy_version', 'N/A')}\n"
            f"Product: {info.get('product_name', 'N/A')}\n"
            f"Uptime: {info.get('uptime')}"
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return f"Error checking health: {str(e)}"


@mcp.tool()
def list_active_mitigations() -> str:
    """Lists all IPs currently under mitigation (protected zones)."""
    try:
        service = Container.get_mitigation_service()
        data = service.list_zones(items=100)
        total = data.get("total", 0)
        zones = data.get("zones", [])

        if total == 0:
            return "No active mitigations found."

        result = f"Found {total} active mitigations:\n"
        for zone in zones:
            mode = zone.get("operational_mode", "N/A")
            result += f"- {zone.get('zone_name')} (mode: {mode})\n"
        return result
    except Exception as e:
        logger.error(f"List mitigations failed: {e}")
        return f"Error listing mitigations: {str(e)}"


@mcp.tool()
def mitigate_ip(ip_address: str, template: str | None = None) -> str:
    """
    All-in-one mitigation for a specific IP address using a configured template.
    - If zone does NOT exist: creates it from the specified template,
      enables monitoring with full indicator coverage, and deploys (syncs)
      to TPS devices automatically.
    - If zone ALREADY exists: re-deploys/syncs to TPS devices to ensure
      the configuration is up to date.

    Args:
        ip_address: IP address to mitigate
        template: Template name to use. If not specified, auto-selects if only one template exists.
    """
    try:
        service = Container.get_mitigation_service()
        result = service.ensure_mitigation(ip_address, template=template)
        return result.get("message", "Unknown result")
    except Exception as e:
        logger.error(f"Mitigation failed for {ip_address} with template {template}: {e}")
        return f"Error executing mitigation: {str(e)}"


@mcp.tool()
def get_zone_status(ip_address: str) -> str:
    """
    Returns the configuration and status of a specific mitigation zone by IP address.
    Useful to check if an IP is protected, its operational mode, and applied services.
    """
    try:
        service = Container.get_mitigation_service()
        status = service.get_zone_status(ip_address)
        if not status:
            return f"No zone found for IP: {ip_address}"

        return (
            f"Zone: {status['zone_name']}\n"
            f"ID: {status['zone_id']}\n"
            f"Mode: {status['operational_mode']}\n"
            f"Services: {status['services_count']} configured\n"
            f"IPs: {', '.join(status.get('ip_list', []))}"
        )
    except Exception as e:
        logger.error(f"Zone status check failed for {ip_address}: {e}")
        return f"Error checking zone status: {str(e)}"


@mcp.tool()
def remove_mitigation(ip_address: str) -> str:
    """
    Stops mitigation for a specific IP address and removes the zone.
    """
    try:
        service = Container.get_mitigation_service()
        result = service.remove_zone(ip_address)
        return result.message
    except Exception as e:
        logger.error(f"Remove mitigation failed for {ip_address}: {e}")
        return f"Error removing mitigation for {ip_address}: {str(e)}"


# Template Management Tools
@mcp.tool()
def get_zone_template(name: str = "default") -> str:
    """
    Retrieves a configured zone template by name.
    Returns the full template configuration including zone and monitor payloads.

    Args:
        name: Template name (default: "default")
    """
    try:
        service = Container.get_template_service()
        template_data = service.get_template(name)

        zone_payload = template_data.get("zone_payload", {})
        monitor_payload = template_data.get("monitor_payload", {})

        services_count = len(zone_payload.get("port", {}).get("zone_service_list", []))
        protection_count = len(monitor_payload.get("protection_values", []))

        return (
            f"Template: {name}\n"
            f"Profile: {zone_payload.get('profile_name', 'N/A')}\n"
            f"Operational Policy: {zone_payload.get('zone_oper_policy', 'N/A')}\n"
            f"Device Group: {zone_payload.get('device_group', 'N/A')}\n"
            f"Services: {services_count}\n"
            f"Protection Values: {protection_count}\n"
            f"Sensitivity: {monitor_payload.get('sensitivity', 'N/A')}"
        )
    except Exception as e:
        logger.error(f"Get template failed for {name}: {e}")
        return f"Error retrieving template '{name}': {str(e)}"


@mcp.tool()
def set_zone_template(template_json: str, name: str = "default") -> str:
    """
    Creates or updates a zone template with validation against A10.
    Validates that all profiles, policies, and device groups exist before saving.

    Args:
        template_json: Complete template as JSON string (must include zone_payload and monitor_payload)
        name: Template name (default: "default")
    """
    try:
        import json

        # Parse JSON
        template_data = json.loads(template_json)

        # Ensure name matches
        template_data["name"] = name

        service = Container.get_template_service()
        result = service.save_template(template_data, name, is_update=False)

        return f"✓ Template '{name}' saved successfully!\n{result.get('message', '')}"
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON for template {name}: {e}")
        return f"Error: Invalid JSON format - {str(e)}"
    except Exception as e:
        logger.error(f"Set template failed for {name}: {e}")
        return f"Error saving template '{name}': {str(e)}"


@mcp.tool()
def list_zone_templates() -> str:
    """
    Lists all available zone templates with their metadata.
    Shows template name, profile, device group, and service counts.
    """
    try:
        service = Container.get_template_service()
        templates = service.list_templates()

        if not templates:
            return "No templates configured. Create one with set_zone_template."

        result = f"Found {len(templates)} template(s):\n\n"
        for tmpl in templates:
            result += (
                f"• {tmpl['name']}\n"
                f"  Profile: {tmpl['profile_name']}\n"
                f"  Services: {tmpl['services_count']}\n"
                f"  Protection Values: {tmpl['protection_values_count']}\n"
                f"  Device Group: {tmpl['device_group'][:16]}...\n\n"
            )

        return result
    except Exception as e:
        logger.error(f"List templates failed: {e}")
        return f"Error listing templates: {str(e)}"


@mcp.tool()
def import_zone_template(ip_address: str, name: str) -> str:
    """
    Imports a template from an existing A10 zone configuration.
    Fetches zone by IP, extracts payloads, removes IP-specific fields, and saves as template.

    Args:
        ip_address: IP of existing zone to import from
        name: Name for the new template
    """
    try:
        service = Container.get_template_service()
        result = service.import_from_zone(ip_address, name)

        return f"✓ Template '{name}' imported from zone {ip_address}!\n{result.get('message', '')}"
    except NotImplementedError:
        return (
            "Import feature will be implemented after template system is fully operational. "
            "Use set_zone_template to create templates manually for now."
        )
    except Exception as e:
        logger.error(f"Import template failed from {ip_address}: {e}")
        return f"Error importing template from {ip_address}: {str(e)}"


if __name__ == "__main__":
    try:
        # Pre-flight check
        client = Container.get_client()
        logger.info(f"Starting A10 Guardian MCP Server (transport={MCP_TRANSPORT})...")

        if MCP_TRANSPORT == "stdio":
            mcp.run()
        else:
            # HTTP transports: "streamable-http", "sse"
            mcp.run(
                transport=MCP_TRANSPORT,
                host=MCP_HOST,
                port=MCP_PORT,
            )
    except Exception as e:
        logger.critical(f"Failed to start MCP Server: {e}")
        sys.exit(1)
