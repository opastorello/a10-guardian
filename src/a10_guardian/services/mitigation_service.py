import copy
import threading

from fastapi import HTTPException
from loguru import logger

from a10_guardian.core.client import A10Client
from a10_guardian.core.config import settings
from a10_guardian.schemas.common import GenericResponse
from a10_guardian.services.notification_service import NotificationService
from a10_guardian.services.template_service import TemplateService

# Per-zone locks to serialize concurrent ip_list mutations within this process.
# Protects against lost updates when multiple clients add/remove IPs on the same
# zone simultaneously. Does NOT protect across multiple replicas — for that,
# move to a distributed lock (Redis SET NX EX) keyed on zone_name.
_ZONE_LOCKS: dict[str, threading.Lock] = {}
_ZONE_LOCKS_MASTER = threading.Lock()


def _get_zone_lock(zone_name: str) -> threading.Lock:
    """Returns (creating if needed) the lock guarding mutations on a given zone."""
    with _ZONE_LOCKS_MASTER:
        lock = _ZONE_LOCKS.get(zone_name)
        if lock is None:
            lock = threading.Lock()
            _ZONE_LOCKS[zone_name] = lock
        return lock


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

    def get_zone_by_name(self, zone_name: str):
        """Finds a specific zone by its zone_name (any name, not just IP).

        Args:
            zone_name (str): Name of the zone (e.g. "On-Demand").

        Returns:
            dict: Zone object if found, None otherwise.
        """
        response = self.client.get("/tps/protected_objects/zones/api/?page=1&items=1000")
        zones = response.get("object_list", [])

        for zone in zones:
            if zone.get("zone_name") == zone_name:
                return zone
        return None

    def has_ip_in_zone(self, zone_name: str, ip: str) -> bool:
        """Checks whether a given IP is present in the zone's ip_list.

        Args:
            zone_name (str): Name of the zone.
            ip (str): IP address to search for.

        Returns:
            bool: True if the IP is present, False otherwise.

        Raises:
            HTTPException: 404 if the zone does not exist.
        """
        zone = self.get_zone_by_name(zone_name)
        if not zone:
            raise HTTPException(status_code=404, detail=f"Zone not found: {zone_name}")

        details = self.get_zone_details(zone.get("id"))
        ip_list = details.get("ip_list") or zone.get("ip_list") or []
        return ip in ip_list

    def add_ip_to_zone(self, zone_name: str, ip: str) -> dict:
        """Adds an IP to the zone's ip_list. Idempotent: returns changed=False if already present.

        Serialized per-zone with a process-local lock to avoid lost updates when
        multiple callers mutate the same zone concurrently. After writing, the
        zone is re-read and a 409 is raised if the new IP is not visible — that
        catches A10-side rejections and changes made outside this API.

        Args:
            zone_name (str): Name of the zone.
            ip (str): IP address to add.

        Returns:
            dict: {zone_name, ip, action: "added", changed: bool, ip_count: int}

        Raises:
            HTTPException: 404 if the zone does not exist; 409 if the post-write
                verification shows the IP did not land in the zone.
        """
        with _get_zone_lock(zone_name):
            zone = self.get_zone_by_name(zone_name)
            if not zone:
                raise HTTPException(status_code=404, detail=f"Zone not found: {zone_name}")

            zone_id = zone.get("id")
            details = self.get_zone_details(zone_id)
            ip_list = list(details.get("ip_list") or [])

            if ip in ip_list:
                return {
                    "zone_name": zone_name,
                    "ip": ip,
                    "action": "added",
                    "changed": False,
                    "ip_count": len(ip_list),
                }

            new_ip_list = [*ip_list, ip]
            payload = copy.deepcopy(details)
            payload["ip_list"] = new_ip_list
            if "input_ips" in payload:
                payload["input_ips"] = new_ip_list

            self.update_zone(zone_id, payload)

            verified = self.get_zone_details(zone_id)
            verified_ip_list = list(verified.get("ip_list") or [])
            if ip not in verified_ip_list:
                logger.bind(audit=True, requester="API").warning(
                    f"Action: Add IP to Zone | Zone: {zone_name} | IP: {ip} | "
                    f"Status: Verification failed (post-write ip_list missing IP)"
                )
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Add of {ip} to zone {zone_name} did not persist. "
                        "Possible concurrent modification — please retry."
                    ),
                )

            logger.bind(audit=True, requester="API").info(
                f"Action: Add IP to Zone | Zone: {zone_name} | IP: {ip} | "
                f"Status: Success | Total IPs: {len(verified_ip_list)}"
            )

            if settings.NOTIFY_ZONE_MODIFIED:
                self.notifier.send_notification(
                    title="Zone IP Added",
                    message=f"IP {ip} added to zone {zone_name}",
                    level="info",
                    fields={
                        "Zone": zone_name,
                        "IP": ip,
                        "Total IPs": str(len(verified_ip_list)),
                    },
                    event_type="zone_modified",
                )

            return {
                "zone_name": zone_name,
                "ip": ip,
                "action": "added",
                "changed": True,
                "ip_count": len(verified_ip_list),
            }

    def remove_ip_from_zone(self, zone_name: str, ip: str) -> dict:
        """Removes an IP from the zone's ip_list.

        Serialized per-zone with a process-local lock; after writing, re-reads
        the zone and raises 409 if the IP is still present.

        Args:
            zone_name (str): Name of the zone.
            ip (str): IP address to remove.

        Returns:
            dict: {zone_name, ip, action: "removed", changed: True, ip_count: int}

        Raises:
            HTTPException: 404 if zone or IP is not found, 422 if IP is the last
                one in the zone, 409 if post-write verification still sees the IP.
        """
        with _get_zone_lock(zone_name):
            zone = self.get_zone_by_name(zone_name)
            if not zone:
                raise HTTPException(status_code=404, detail=f"Zone not found: {zone_name}")

            zone_id = zone.get("id")
            details = self.get_zone_details(zone_id)
            ip_list = list(details.get("ip_list") or [])

            if ip not in ip_list:
                raise HTTPException(status_code=404, detail=f"IP {ip} not present in zone {zone_name}")

            if len(ip_list) <= 1:
                raise HTTPException(
                    status_code=422,
                    detail=f"Cannot remove last IP from zone {zone_name}. Delete the zone instead.",
                )

            new_ip_list = [x for x in ip_list if x != ip]
            payload = copy.deepcopy(details)
            payload["ip_list"] = new_ip_list
            if "input_ips" in payload:
                payload["input_ips"] = new_ip_list

            self.update_zone(zone_id, payload)

            verified = self.get_zone_details(zone_id)
            verified_ip_list = list(verified.get("ip_list") or [])
            if ip in verified_ip_list:
                logger.bind(audit=True, requester="API").warning(
                    f"Action: Remove IP from Zone | Zone: {zone_name} | IP: {ip} | "
                    f"Status: Verification failed (IP still present after write)"
                )
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Remove of {ip} from zone {zone_name} did not persist. "
                        "Possible concurrent modification — please retry."
                    ),
                )

            logger.bind(audit=True, requester="API").info(
                f"Action: Remove IP from Zone | Zone: {zone_name} | IP: {ip} | "
                f"Status: Success | Total IPs: {len(verified_ip_list)}"
            )

            if settings.NOTIFY_ZONE_MODIFIED:
                self.notifier.send_notification(
                    title="Zone IP Removed",
                    message=f"IP {ip} removed from zone {zone_name}",
                    level="warning",
                    fields={
                        "Zone": zone_name,
                        "IP": ip,
                        "Total IPs": str(len(verified_ip_list)),
                    },
                    event_type="zone_modified",
                )

            return {
                "zone_name": zone_name,
                "ip": ip,
                "action": "removed",
                "changed": True,
                "ip_count": len(verified_ip_list),
            }

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

    def is_under_attack(self, ip: str) -> dict:
        """Checks if the /24 block of a given IP is currently under attack.

        A zone is considered under attack if:
        1. Its operational_mode is "mitigation" (auto-mitigation active), OR
        2. There is an ongoing incident for that zone (attack detected in monitor mode)

        Args:
            ip (str): Any IP address (e.g. 181.215.253.2).

        Returns:
            dict: {"under_attack": bool, "monitored": bool, "ip": str, "block": str}
        """
        parts = ip.strip().split(".")
        if len(parts) != 4:
            raise ValueError(f"Invalid IP address: {ip}")

        block = f"{parts[0]}.{parts[1]}.{parts[2]}.0-255"

        # Check 1: zone operational_mode
        response = self.client.get("/tps/protected_objects/zones/api/?page=1&items=1000")
        zones = response.get("object_list", [])

        monitored = False
        in_mitigation_mode = False
        for zone in zones:
            if zone.get("zone_name") == block:
                monitored = True
                in_mitigation_mode = zone.get("operational_mode") == "mitigation"
                break

        if in_mitigation_mode:
            return {"under_attack": True, "monitored": True, "ip": ip, "block": block}

        if not monitored:
            return {"under_attack": False, "monitored": False, "ip": ip, "block": block}

        # Check 2: ongoing incidents for this zone (zone in monitor mode but attack active)
        try:
            inc_response = self.client.get(
                "/tps/zone/incident/ongoing/json/",
                params={"page": 1, "items": 100, "tps_incident_active": "Ongoing"},
            )
            for incident in inc_response.get("object_list", []):
                zone_name = incident.get("zone") or incident.get("zone_name", "")
                if zone_name == block:
                    return {"under_attack": True, "monitored": True, "ip": ip, "block": block}
        except Exception:
            pass  # If incidents check fails, fall back to operational_mode result

        return {"under_attack": False, "monitored": True, "ip": ip, "block": block}

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
        if settings.NOTIFY_MITIGATION_STOP:
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
