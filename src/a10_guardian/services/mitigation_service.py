import copy

from fastapi import HTTPException
from loguru import logger

from a10_guardian.core.client import A10Client
from a10_guardian.core.config import settings
from a10_guardian.schemas.common import GenericResponse
from a10_guardian.services.notification_service import NotificationService
from a10_guardian.services.template_service import TemplateService


class MitigationService:
    """Service for managing DDoS mitigation zones and monitoring.

    Args:
        client (A10Client): Authenticated A10 client.
        notifier (NotificationService): Service to send external notifications.
    """

    def __init__(self, client: A10Client, notifier: NotificationService = None):
        self.client = client
        self.notifier = notifier or NotificationService()

    def list_zones(self, page: int = 1, items: int = 40) -> dict:
        """Lists protected zones with pagination.

        Returns a processed response with zone_name, zone_id, and operational_mode.

        Args:
            page (int): Page number (default: 1).
            items (int): Items per page (default: 40).

        Returns:
            dict: Processed zone list matching ZoneListResponse.
        """
        raw = self.client.get(f"/tps/protected_objects/zones/api/?page={page}&items={items}")
        total = raw.get("total", 0)
        object_list = raw.get("object_list", [])

        zones = []
        for zone in object_list:
            zones.append(
                {
                    "zone_name": zone.get("zone_name"),
                    "zone_id": zone.get("id"),
                    "operational_mode": zone.get("operational_mode"),
                }
            )

        return {
            "total": total,
            "page": page,
            "items": items,
            "zones": zones,
        }

    def get_zone_by_ip(self, ip: str):
        """Finds a specific zone by its IP address (Zone Name).

        Args:
            ip (str): IP address of the zone.

        Returns:
            dict: Zone object if found, None otherwise.
        """
        response = self.client.get("/tps/protected_objects/zones/api/?page=1&items=1000")
        zones = response.get("object_list", [])

        for zone in zones:
            if zone.get("zone_name") == ip:
                return zone
        return None

    def get_zone_status(self, ip: str) -> dict | None:
        """Gets the processed status of a zone by IP address.

        Returns:
            dict: Zone status matching ZoneStatusResponse, or None if not found.
        """
        zone = self.get_zone_by_ip(ip)
        if not zone:
            return None

        zone_id = zone.get("id")
        details = self.get_zone_details(zone_id)

        # Count services from zone_service_list or from uuid_dict entries
        services_count = len(details.get("zone_service_list", []))
        if services_count == 0:
            uuid_dict = details.get("uuid_dict", {})
            for device_data in uuid_dict.values():
                service_data = device_data.get("service", {})
                services_count = max(services_count, len(service_data))

        return {
            "zone_name": ip,
            "zone_id": zone_id,
            "operational_mode": details.get("operational_mode", "unknown"),
            "services_count": services_count,
            "ip_list": details.get("ip_list", zone.get("ip_list", [])),
        }

    def get_zone_details(self, zone_id: str):
        """Fetches the full configuration details of a specific zone.

        Args:
            zone_id (str): The UUID of the zone.

        Returns:
            dict: Full zone configuration.
        """
        return self.client.get(f"/tps/protected_objects/zones/api/{zone_id}/")

    def create_zone_raw(self, payload: dict):
        """Creates a new protected zone using a raw dictionary payload.

        Args:
            payload (dict): Raw zone configuration.

        Returns:
            dict: API response.
        """
        response = self.client.post("/tps/protected_objects/zones/api/create/", json_data=payload)

        zone_name = payload.get("zone_name", "Unknown")
        logger.bind(audit=True, requester="API").info(f"Action: Create Zone | Target: {zone_name} | Status: Success")
        return response

    def update_zone(self, zone_id: str, payload: dict):
        """Updates an existing zone configuration.

        Args:
            zone_id (str): The internal ID of the zone.
            payload (dict): Full zone configuration to update.

        Returns:
            dict: API response.
        """
        response = self.client.post(f"/tps/protected_objects/zones/api/{zone_id}/", json_data=payload)
        logger.bind(audit=True, requester="API").info(f"Action: Update Zone | ID: {zone_id} | Status: Success")
        return response

    def ensure_mitigation(self, ip_address: str, template: str | None = None) -> dict:
        """
        All-in-one mitigation for a specific IP.
        - If zone exists: re-deploys/syncs to TPS devices (always ensures sync).
        - If zone missing: creates zone + monitor + deploy from configured template.

        Args:
            ip_address: IP to mitigate
            template: Template name to use. If None, auto-selects if only one template exists.

        Returns a dict with 'status', 'message', 'zone_id'.
        """
        try:
            # Initialize template service
            template_service = TemplateService(self.client, self.notifier)

            # Auto-select template if not specified
            if template is None:
                templates = template_service.list_templates()
                if len(templates) == 0:
                    raise Exception(
                        "No templates configured. Create at least one template using POST /api/v1/templates/<name>"
                    )
                elif len(templates) == 1:
                    template = templates[0]["name"]
                    logger.info(f"Auto-selected template '{template}' (only one available)")
                else:
                    raise Exception(
                        f"Multiple templates available ({len(templates)}). "
                        f"Please specify one: {', '.join([t['name'] for t in templates])}"
                    )

            # Load template
            template_data = template_service.get_template(template)

            existing = self.get_zone_by_ip(ip_address)
            if existing:
                zone_id = existing.get("id")
                details = self.get_zone_details(zone_id)
                current_mode = details.get("operational_mode")
                services_count = len(details.get("zone_service_list", []))
                if services_count == 0:
                    uuid_dict = details.get("uuid_dict", {})
                    for device_data in uuid_dict.values():
                        services_count = max(services_count, len(device_data.get("service", {})))
                profile = details.get("profile_name", "N/A")

                # Use monitor_payload from template
                monitor_payload = copy.deepcopy(template_data["monitor_payload"])
                self.start_monitoring(zone_id, monitor_payload)

                logger.bind(audit=True, requester="API").info(
                    f"Action: Re-deploy/Sync Zone | Target: {ip_address} | Zone ID: {zone_id} | "
                    f"Mode: {current_mode} | Template: {template}"
                )

                # Send notification only if enabled
                if settings.NOTIFY_MITIGATION_START:
                    self.notifier.send_notification(
                        title="Mitigation Re-deployed",
                        message=f"Protection re-synced for existing zone (was in {current_mode} mode)",
                        level="info",
                        fields={
                            "IP": ip_address,
                            "Template": template,
                            "Zone ID": zone_id[:8],
                            "Mode": current_mode,
                            "Services": str(services_count),
                            "Profile": profile,
                        },
                        event_type="mitigation_start",
                    )
                return {
                    "status": "success",
                    "message": (
                        f"Zone {ip_address} already exists (mode: {current_mode}). Re-deployed/synced to TPS devices."
                    ),
                    "zone_id": zone_id,
                }

            # Use zone_payload from template
            zone_payload = copy.deepcopy(template_data["zone_payload"])
            zone_payload["zone_name"] = ip_address
            zone_payload["ip_list"] = [ip_address]
            zone_payload["input_ips"] = [ip_address]
            services_count = len(zone_payload.get("port", {}).get("zone_service_list", []))
            profile = zone_payload.get("profile_name", "N/A")

            resp_create = self.create_zone_raw(zone_payload)
            zone_id = resp_create.get("id")

            if not zone_id:
                raise Exception(f"Failed to create zone: {resp_create}")

            # Use monitor_payload from template
            monitor_payload = copy.deepcopy(template_data["monitor_payload"])
            self.start_monitoring(zone_id, monitor_payload)

            # Send notification only if enabled
            if settings.NOTIFY_MITIGATION_START:
                self.notifier.send_notification(
                    title="Mitigation Started",
                    message=f"Protection activated using template '{template}'",
                    level="warning",
                    fields={
                        "IP": ip_address,
                        "Template": template,
                        "Zone ID": zone_id[:8],
                        "Services": str(services_count),
                        "Profile": profile,
                    },
                    event_type="mitigation_start",
                )
            msg = f"Started mitigation for {ip_address}. Created from template '{template}' + Deployed to TPS."
            return {
                "status": "success",
                "message": msg,
                "zone_id": zone_id,
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Error ensuring mitigation for {ip_address}: {str(e)}",
                "zone_id": None,
            }

    def start_monitoring(self, zone_id: str, monitor_config):
        """Enables monitoring (learning mode) for a created zone and deploys it.

        Args:
            zone_id (str): The internal ID of the zone.
            monitor_config (dict): Configuration for the monitor.

        Returns:
            dict: API response.
        """
        url = f"/tps/protected_objects/zones/api/{zone_id}/monitor/"
        payload = monitor_config.model_dump() if hasattr(monitor_config, "model_dump") else monitor_config
        return self.client.post(url, json_data=payload)

    def remove_zone(self, ip: str) -> GenericResponse:
        """Removes a protected zone by IP address.

        Args:
            ip (str): IP address to unprotect.

        Returns:
            GenericResponse: Status message.

        Raises:
            HTTPException: If the zone is not found (404).
        """
        zone = self.get_zone_by_ip(ip)

        if not zone:
            raise HTTPException(status_code=404, detail=f"Zone not found for IP: {ip}")

        zone_id = zone.get("id")
        zone_name = zone.get("zone_name")
        mode = zone.get("operational_mode", "N/A")

        payload = {"object_ids": [{"detector_id": None, "id": zone_id, "zone_name": zone_name}]}

        self.client.delete("/tps/protected_objects/zones/api/?force_delete=false", json_data=payload)
        logger.bind(audit=True, requester="API").info(f"Action: Delete Zone | Target: {ip} | Status: Success")
        self.notifier.send_notification(
            title="Mitigation Stopped",
            message=f"Protection removed (zone was in {mode} mode)",
            level="error",
            fields={
                "IP": ip,
                "Zone ID": zone_id[:8],
                "Mode": mode,
            },
            event_type="mitigation_stop",
        )
        return GenericResponse(message=f"Zone {ip} removed successfully", status="deleted")
