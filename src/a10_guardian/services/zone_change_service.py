"""Zone Change Detection Service

Monitors A10 TPS device for zone configuration changes made outside the API.
Detects zone creation, modification, and deletion events and sends notifications.
"""

import json
from typing import Any

from loguru import logger

from a10_guardian.core.client import A10Client
from a10_guardian.core.config import settings
from a10_guardian.services.notification_service import NotificationService


class ZoneChangeService:
    """Service for monitoring and detecting zone configuration changes."""

    def __init__(self, client: A10Client, notifier: NotificationService):
        """Initialize the zone change service.

        Args:
            client: A10 API client for fetching zone data
            notifier: Notification service for sending alerts
        """
        self.client = client
        self.notifier = notifier
        self.known_zones: dict[str, dict[str, Any]] = {}
        # Structure: {zone_id: {"snapshot": {...}, "first_seen": timestamp}}

    def fetch_all_zones(self) -> dict[str, dict]:
        """Fetch all zones from A10 device with pagination.

        Returns:
            Dictionary mapping zone_id to full zone configuration
        """
        all_zones = {}
        page = 1
        items_per_page = 100

        while True:
            # Fetch paginated zone list
            response = self.client.get(f"/tps/protected_objects/zones/api/?page={page}&items={items_per_page}")

            logger.debug(f"Zone API response keys: {list(response.keys()) if response else 'None'}")
            logger.debug(f"Zone API response type: {type(response)}")

            if not response or "object_list" not in response:
                response_keys = list(response.keys()) if response else "None"
                logger.warning(f"No 'object_list' in response. Response keys: {response_keys}")
                break

            zones = response.get("object_list", [])
            if not zones:
                break

            # Fetch full configuration for each zone
            for zone_summary in zones:
                zone_id = zone_summary.get("id")
                if not zone_id:
                    continue

                try:
                    # Get detailed zone config
                    zone_detail = self.client.get(f"/tps/protected_objects/zones/api/{zone_id}/")
                    if zone_detail:
                        all_zones[zone_id] = zone_detail
                except Exception as e:
                    logger.warning(f"Failed to fetch zone {zone_id}: {e}")
                    # Use minimal data from list endpoint
                    all_zones[zone_id] = zone_summary

            # Check if there are more pages
            if len(zones) < items_per_page:
                break

            page += 1

        logger.info(f"Fetched {len(all_zones)} zones from A10 device")
        return all_zones

    def normalize_zone_for_comparison(self, zone: dict) -> dict:
        """Normalize zone config by removing volatile fields.

        Args:
            zone: Raw zone configuration

        Returns:
            Normalized zone config with volatile fields removed
        """
        normalized = zone.copy()

        # Remove timestamp fields (these change frequently)
        volatile_fields = [
            "created",
            "created_time",
            "modified",
            "modified_time",
            "last_modified",
            "updated_at",
            "stats",
            "counters",
            "runtime_stats",
        ]

        for field in volatile_fields:
            normalized.pop(field, None)

        return normalized

    def detect_zone_changes(self, current_zones: dict[str, dict]) -> tuple[set[str], set[str], set[str]]:
        """Detect changes between current and known zones.

        Args:
            current_zones: Current zone configurations from A10 device

        Returns:
            Tuple of (new_zone_ids, deleted_zone_ids, modified_zone_ids)
        """
        current_ids = set(current_zones.keys())
        known_ids = set(self.known_zones.keys())

        # New zones (created outside API)
        new_ids = current_ids - known_ids

        # Deleted zones (removed outside API)
        deleted_ids = known_ids - current_ids

        # Modified zones (configuration changed)
        modified_ids = set()
        for zone_id in current_ids & known_ids:
            old_normalized = self.normalize_zone_for_comparison(self.known_zones[zone_id]["snapshot"])
            new_normalized = self.normalize_zone_for_comparison(current_zones[zone_id])

            if old_normalized != new_normalized:
                modified_ids.add(zone_id)

        return new_ids, deleted_ids, modified_ids

    def get_zone_change_user(self, zone_id: str, event_type: str, lookback_minutes: int = 5) -> str | None:
        """Query audit logs to identify who made the zone change.

        Args:
            zone_id: Zone identifier to search for
            event_type: Type of event (created, updated, deleted)
            lookback_minutes: How far back to search (default: 5 minutes)

        Returns:
            Username who made the change, or None if not found
        """
        try:
            # Map our event types to A10 audit event types
            event_type_map = {
                "created": "a10.agalaxy.tps.ddos.zone.created",
                "updated": "a10.agalaxy.tps.ddos.zone.updated",
                "deleted": "a10.agalaxy.tps.ddos.zone.deleted",
            }

            target_event_type = event_type_map.get(event_type)
            if not target_event_type:
                return None

            # Fetch recent audit events (search last 100 events)
            response = self.client.get("/dashboard/audit/events/json/?page=1&items=100")

            if not response or "object_list" not in response:
                return None

            events = response.get("object_list", [])

            # Search for matching zone event
            for event in events:
                if event.get("type") != target_event_type:
                    continue

                # Parse event_data JSON string
                event_data_str = event.get("event_data", "")
                if not event_data_str:
                    continue

                try:
                    event_data = json.loads(event_data_str)
                    event_zone_id = event_data.get("zone_id")
                    user_id = event_data.get("user_id")

                    if event_zone_id == zone_id and user_id:
                        # Filter out changes made by the API itself
                        if user_id == settings.A10_USERNAME:
                            logger.debug(
                                f"Found {event_type} event for zone {zone_id[:12]}... by API user ({user_id}), "
                                f"skipping notification (change made by API itself)"
                            )
                            return None

                        logger.debug(f"Found {event_type} event for zone {zone_id[:12]}... by external user: {user_id}")
                        return user_id

                except json.JSONDecodeError:
                    continue

            logger.debug(f"No audit log entry found for zone {zone_id[:12]}... event type: {event_type}")
            return None

        except Exception as e:
            logger.warning(f"Failed to query audit logs for user attribution: {e}")
            return None

    def generate_change_summary(self, old_zone: dict, new_zone: dict) -> str:
        """Generate human-readable summary of zone configuration changes.

        Args:
            old_zone: Previous zone configuration
            new_zone: Current zone configuration

        Returns:
            Change summary string
        """
        changes = []

        # Check operational mode change
        old_mode = old_zone.get("operational_mode")
        new_mode = new_zone.get("operational_mode")
        if old_mode != new_mode:
            changes.append(f"Mode: {old_mode} → {new_mode}")

        # Check profile change
        old_profile = old_zone.get("profile_name")
        new_profile = new_zone.get("profile_name")
        if old_profile != new_profile:
            changes.append(f"Profile: {old_profile} → {new_profile}")

        # Check policy change
        old_policy = old_zone.get("zone_oper_policy")
        new_policy = new_zone.get("zone_oper_policy")
        if old_policy != new_policy:
            changes.append(f"Policy: {old_policy} → {new_policy}")

        # Check service count change
        old_services = len(old_zone.get("zone_services", []))
        new_services = len(new_zone.get("zone_services", []))
        if old_services != new_services:
            changes.append(f"Services: {old_services} → {new_services}")

        if not changes:
            return "Configuration updated"

        return ", ".join(changes)

    def notify_zone_created(self, zone: dict):
        """Send notification for newly created zone.

        Args:
            zone: Zone configuration
        """
        if not settings.NOTIFY_ZONE_CREATED:
            return

        zone_id = zone.get("id", "Unknown")
        zone_name = zone.get("zone_name", "Unknown")
        ip_address = zone_name.split("-")[0] if "-" in zone_name else zone_name
        operational_mode = zone.get("operational_mode", "Unknown")
        profile_name = zone.get("profile_name", "None")
        service_count = len(zone.get("zone_services", []))

        # Query audit logs for user attribution
        user = self.get_zone_change_user(zone_id, "created")

        # Skip notification if change was made by API itself
        if user is None:
            logger.debug(f"Zone created by API itself ({zone_id[:12]}...), skipping external notification")
            return

        logger.warning(f"NEW ZONE DETECTED: {ip_address} - {zone_id} (by {user})")

        fields = {
            "IP": ip_address,
            "Zone ID": zone_id[:12] + "..." if len(zone_id) > 12 else zone_id,
            "Mode": operational_mode,
            "Profile": profile_name,
            "Services": str(service_count),
            "Created By": user,
        }

        self.notifier.send_notification(
            title="Zone Created",
            message="New protection zone detected (created outside API)",
            level="success",
            event_type="zone_created",
            fields=fields,
        )

        # Audit log
        logger.info(
            f"Zone Created (External): {ip_address} | "
            f"ID: {zone_id} | Mode: {operational_mode} | Services: {service_count} | User: {user}"
        )

    def notify_zone_modified(self, zone_id: str, old_zone: dict, new_zone: dict):
        """Send notification for modified zone configuration.

        Args:
            zone_id: Zone identifier
            old_zone: Previous zone configuration
            new_zone: Current zone configuration
        """
        if not settings.NOTIFY_ZONE_MODIFIED:
            return

        zone_name = new_zone.get("zone_name", "Unknown")
        ip_address = zone_name.split("-")[0] if "-" in zone_name else zone_name
        change_summary = self.generate_change_summary(old_zone, new_zone)
        operational_mode = new_zone.get("operational_mode", "Unknown")
        profile_name = new_zone.get("profile_name", "None")

        # Query audit logs for user attribution
        user = self.get_zone_change_user(zone_id, "updated")

        # Skip notification if change was made by API itself
        if user is None:
            logger.debug(f"Zone modified by API itself ({zone_id[:12]}...), skipping external notification")
            return

        logger.warning(f"ZONE MODIFIED: {ip_address} - {zone_id} - {change_summary} (by {user})")

        fields = {
            "IP": ip_address,
            "Zone ID": zone_id[:12] + "..." if len(zone_id) > 12 else zone_id,
            "Changes": change_summary,
            "Current Mode": operational_mode,
            "Profile": profile_name,
            "Modified By": user,
        }

        self.notifier.send_notification(
            title="Zone Modified",
            message="Configuration changed (modified outside API)",
            level="info",
            event_type="zone_modified",
            fields=fields,
        )

        # Audit log
        logger.info(
            f"Zone Modified (External): {ip_address} | ID: {zone_id} | Changes: {change_summary} | User: {user}"
        )

    def notify_zone_deleted(self, zone_id: str, zone: dict):
        """Send notification for deleted zone.

        Args:
            zone_id: Zone identifier
            zone: Zone configuration (from snapshot before deletion)
        """
        if not settings.NOTIFY_ZONE_DELETED:
            return

        zone_name = zone.get("zone_name", "Unknown")
        ip_address = zone_name.split("-")[0] if "-" in zone_name else zone_name
        operational_mode = zone.get("operational_mode", "Unknown")

        # Query audit logs for user attribution
        user = self.get_zone_change_user(zone_id, "deleted")

        # Skip notification if change was made by API itself
        if user is None:
            logger.debug(f"Zone deleted by API itself ({zone_id[:12]}...), skipping external notification")
            return

        logger.warning(f"ZONE DELETED: {ip_address} - {zone_id} (by {user})")

        fields = {
            "IP": ip_address,
            "Zone ID": zone_id[:12] + "..." if len(zone_id) > 12 else zone_id,
            "Previous Mode": operational_mode,
            "Deleted By": user,
        }

        self.notifier.send_notification(
            title="Zone Deleted",
            message="Protection zone removed (deleted outside API)",
            level="warning",
            event_type="zone_deleted",
            fields=fields,
        )

        # Audit log
        logger.info(f"Zone Deleted (External): {ip_address} | ID: {zone_id} | Mode: {operational_mode} | User: {user}")
