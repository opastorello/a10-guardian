"""Service for monitoring DDoS attacks and incidents on A10 Thunder TPS."""

from loguru import logger

from a10_guardian.core.client import A10Client
from a10_guardian.core.config import settings
from a10_guardian.services.notification_service import NotificationService


def _format_duration(seconds: int) -> str:
    """Format a duration in seconds to a human-readable string.

    Examples: 45 -> "45s", 330 -> "5m 30s", 3900 -> "1h 5m"
    """
    if seconds < 60:
        return f"{seconds}s"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    secs = seconds % 60
    return f"{minutes}m {secs}s" if secs > 0 else f"{minutes}m"


class AttackService:
    """Monitors DDoS attacks/incidents and sends real-time notifications."""

    def __init__(self, client: A10Client, notifier: NotificationService):
        self.client = client
        self.notifier = notifier

    def get_ongoing_incidents(self, page: int = 1, items: int = 100) -> dict:
        """Fetch ongoing DDoS incidents from A10 Thunder TPS.

        Args:
            page: Page number for pagination
            items: Items per page (max 100)

        Returns:
            dict with incident list and metadata
        """
        try:
            params = {
                "page": page,
                "items": items,
                "tps_incident_active": "Ongoing",
                "sort_ordering": "DESC",
            }

            response = self.client.get("/tps/zone/incident/ongoing/json/", params=params)

            total = response.get("total", 0)
            incidents = response.get("object_list", [])

            logger.info(f"Fetched {len(incidents)} ongoing incidents (total: {total})")

            return {
                "total": total,
                "page": page,
                "items_per_page": items,
                "incidents": incidents,
            }

        except Exception as e:
            logger.error(f"Failed to fetch ongoing incidents: {e}")
            return {"total": 0, "page": page, "items_per_page": items, "incidents": []}

    def get_incident_stats(self, incident_id: str) -> dict | None:
        """Get detailed statistics for a specific incident.

        Args:
            incident_id: UUID of the incident

        Returns:
            dict with incident statistics or None
        """
        try:
            stats = self.client.get(f"/tps/zone/incident/{incident_id}/stats/")
            logger.info(f"Fetched stats for incident {incident_id}")
            return stats
        except Exception as e:
            logger.error(f"Failed to fetch stats for incident {incident_id}: {e}")
            return None

    def get_incident_details(self, incident_id: str) -> dict | None:
        """Get full JSON details for a specific incident.

        Args:
            incident_id: UUID of the incident

        Returns:
            dict with incident details or None
        """
        try:
            details = self.client.get(f"/tps/zone/incident/{incident_id}/json/")
            logger.info(f"Fetched details for incident {incident_id}")
            return details
        except Exception as e:
            logger.error(f"Failed to fetch details for incident {incident_id}: {e}")
            return None

    def notify_attack_detected(self, incident: dict):
        """Send notification when a new attack is detected.

        Args:
            incident: Incident data from A10 (object_list item)
        """
        if not settings.NOTIFY_ATTACK_DETECTED:
            return

        zone_name = incident.get("zone") or incident.get("zone_name", "Unknown")
        attack_type = incident.get("attack_type", "Unknown")
        start_time = incident.get("start_time", "Unknown")
        service = incident.get("service", "N/A")
        incident_name = incident.get("name", "N/A")

        fields = {
            "Target IP": zone_name,
            "Attack Type": attack_type,
            "Service": service,
            "Started": start_time,
        }

        self.notifier.send_notification(
            title="DDoS Attack Detected",
            message=f"High-volume attack detected on {zone_name} - mitigation activated",
            level="error",
            fields=fields,
            event_type="attack_detected",
        )

        logger.bind(audit=True, requester="system").warning(
            f"Action: Attack Detected | Target: {zone_name} | Type: {attack_type} | Incident: {incident_name}"
        )

    def notify_attack_mitigated(self, incident: dict, duration_seconds: int):
        """Send notification when an attack is mitigated/ended.

        Args:
            incident: Incident data from A10
            duration_seconds: Attack duration in seconds
        """
        if not settings.NOTIFY_ATTACK_MITIGATED:
            return

        zone_name = incident.get("zone") or incident.get("zone_name", "Unknown")
        attack_type = incident.get("attack_type", "Unknown")
        incident_name = incident.get("name", "N/A")

        duration_str = _format_duration(duration_seconds)

        fields = {
            "Target IP": zone_name,
            "Attack Type": attack_type,
            "Duration": duration_str,
        }

        self.notifier.send_notification(
            title="Attack Mitigated",
            message=f"Attack on {zone_name} successfully mitigated after {duration_str}",
            level="success",
            fields=fields,
            event_type="attack_mitigated",
        )

        logger.bind(audit=True, requester="system").info(
            f"Action: Attack Mitigated | Target: {zone_name} | Duration: {duration_str} | Incident: {incident_name}"
        )

    def notify_attack_ongoing(self, incident: dict, elapsed_seconds: int):
        """Send periodic notification for long-running attacks.

        Args:
            incident: Incident data from A10
            elapsed_seconds: Time since attack started
        """
        if not settings.NOTIFY_ATTACK_ONGOING:
            return

        zone_name = incident.get("zone") or incident.get("zone_name", "Unknown")
        attack_type = incident.get("attack_type", "Unknown")
        incident_name = incident.get("name", "N/A")

        duration_str = _format_duration(elapsed_seconds)

        fields = {
            "Target IP": zone_name,
            "Attack Type": attack_type,
            "Duration": duration_str,
            "Status": "Still under attack",
        }

        self.notifier.send_notification(
            title="Attack Still Ongoing",
            message=f"Attack on {zone_name} continues - mitigation active for {duration_str}",
            level="warning",
            fields=fields,
            event_type="attack_ongoing",
        )

        logger.bind(audit=True, requester="system").warning(
            f"Action: Attack Ongoing | Target: {zone_name} | Duration: {duration_str} | Incident: {incident_name}"
        )
