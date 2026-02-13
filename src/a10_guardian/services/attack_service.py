"""Service for monitoring DDoS attacks and incidents on A10 Thunder TPS."""

from loguru import logger

from a10_guardian.core.client import A10Client
from a10_guardian.core.config import settings
from a10_guardian.services.notification_service import NotificationService


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

            total = response.get("total_items", 0)
            incidents = response.get("incident_list", [])

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
            incident: Incident data from A10
        """
        if not settings.NOTIFY_ATTACK_DETECTED:
            return

        zone_name = incident.get("zone_name", "Unknown")
        severity = incident.get("severity", "Unknown")
        start_time = incident.get("start_time", "Unknown")
        incident_id = incident.get("incident_id", "N/A")

        # Get additional stats if available
        stats = self.get_incident_stats(incident_id) if incident_id != "N/A" else None

        fields = {
            "Target IP": zone_name,
            "Severity": severity,
            "Started": start_time,
            "Incident ID": incident_id[:8] + "..." if len(incident_id) > 8 else incident_id,
        }

        # Add traffic stats if available
        if stats:
            if "peak_pps" in stats:
                fields["Peak Traffic"] = f"{stats['peak_pps']:,} pps"
            if "attack_types" in stats:
                fields["Attack Types"] = ", ".join(stats["attack_types"][:3])  # Top 3

        self.notifier.send_notification(
            title="DDoS Attack Detected",
            message=f"High-volume attack detected on {zone_name} - mitigation activated",
            level="error",
            fields=fields,
            event_type="attack_detected",
        )

        logger.bind(audit=True).warning(
            f"Action: Attack Detected | Target: {zone_name} | Severity: {severity} | Incident: {incident_id}"
        )

    def notify_attack_mitigated(self, incident: dict, duration_seconds: int):
        """Send notification when an attack is mitigated/ended.

        Args:
            incident: Incident data from A10
            duration_seconds: Attack duration in seconds
        """
        if not settings.NOTIFY_ATTACK_MITIGATED:
            return

        zone_name = incident.get("zone_name", "Unknown")
        severity = incident.get("severity", "Unknown")
        incident_id = incident.get("incident_id", "N/A")

        # Format duration
        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        duration_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

        fields = {
            "Target IP": zone_name,
            "Severity": severity,
            "Duration": duration_str,
            "Incident ID": incident_id[:8] + "..." if len(incident_id) > 8 else incident_id,
        }

        self.notifier.send_notification(
            title="Attack Mitigated",
            message=f"Attack on {zone_name} successfully mitigated after {duration_str}",
            level="success",
            fields=fields,
            event_type="attack_mitigated",
        )

        logger.bind(audit=True).info(
            f"Action: Attack Mitigated | Target: {zone_name} | Duration: {duration_str} | Incident: {incident_id}"
        )

    def notify_attack_ongoing(self, incident: dict, elapsed_seconds: int):
        """Send periodic notification for long-running attacks.

        Args:
            incident: Incident data from A10
            elapsed_seconds: Time since attack started
        """
        if not settings.NOTIFY_ATTACK_ONGOING:
            return

        zone_name = incident.get("zone_name", "Unknown")
        severity = incident.get("severity", "Unknown")
        incident_id = incident.get("incident_id", "N/A")

        # Only notify every 15 minutes for ongoing attacks
        if elapsed_seconds % 900 != 0:  # 900s = 15min
            return

        hours = elapsed_seconds // 3600
        minutes = (elapsed_seconds % 3600) // 60
        duration_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

        fields = {
            "Target IP": zone_name,
            "Severity": severity,
            "Duration": duration_str,
            "Status": "Still under attack",
            "Incident ID": incident_id[:8] + "..." if len(incident_id) > 8 else incident_id,
        }

        self.notifier.send_notification(
            title="Attack Still Ongoing",
            message=f"Attack on {zone_name} continues - mitigation active for {duration_str}",
            level="warning",
            fields=fields,
            event_type="attack_ongoing",
        )

        logger.bind(audit=True).warning(
            f"Action: Attack Ongoing | Target: {zone_name} | Duration: {duration_str} | Incident: {incident_id}"
        )
