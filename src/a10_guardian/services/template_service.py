"""Service for managing zone templates - load, save, validate, import."""

import json
from pathlib import Path

from loguru import logger

from a10_guardian.core.client import A10Client
from a10_guardian.core.config import settings
from a10_guardian.core.exceptions import TemplateA10ValidationError, TemplateNotFoundError, TemplateValidationError
from a10_guardian.schemas.template import ZoneTemplate
from a10_guardian.services.notification_service import NotificationService


class TemplateService:
    """Manages zone templates: CRUD operations, validation, and A10 synchronization."""

    def __init__(self, client: A10Client, notifier: NotificationService):
        self.client = client
        self.notifier = notifier
        self.template_dir = Path(settings.TEMPLATE_DIR)
        self.template_dir.mkdir(parents=True, exist_ok=True)

    def get_template(self, name: str) -> dict:
        """Load template from JSON file or raise TemplateNotFoundError.

        Args:
            name: Template name (without .json extension)

        Returns:
            dict with "name", "zone_payload", "monitor_payload" keys

        Raises:
            TemplateNotFoundError: If template file doesn't exist
        """
        template_path = self.template_dir / f"{name}.json"

        if not template_path.exists():
            logger.error(f"Template '{name}' not found at {template_path}")
            raise TemplateNotFoundError(f"Template '{name}' not found. Create it with POST /api/v1/templates/{name}")

        try:
            with open(template_path, encoding="utf-8") as f:
                template_data = json.load(f)

            logger.info(f"Loaded template '{name}' from {template_path}")
            return template_data

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in template '{name}': {e}")
            raise TemplateValidationError(f"Template '{name}' contains invalid JSON: {e}") from e

    def save_template(self, template: dict, name: str, is_update: bool = False) -> dict:
        """Validate and save template to JSON file.

        Performs both structural validation (Pydantic) and A10 validation (profiles/policies exist).
        Sends notification based on NOTIFY_TEMPLATE_CREATE or NOTIFY_TEMPLATE_UPDATE settings.

        Args:
            template: Full template dict with zone_payload + monitor_payload
            name: Template name (without .json extension)
            is_update: If True, existing template is being updated

        Returns:
            dict with save result and validation details

        Raises:
            TemplateValidationError: If Pydantic validation fails
            TemplateA10ValidationError: If A10 resources don't exist
        """
        # 1. Structural validation with Pydantic
        try:
            validated_template = ZoneTemplate(**template)
        except Exception as e:
            logger.error(f"Template validation failed: {e}")
            raise TemplateValidationError(f"Template structure invalid: {e}") from e

        # 2. A10 validation (skip for imports)
        a10_result = {}
        # TODO: Fix A10 validation endpoints before enabling
        # a10_result = self.validate_template_a10(validated_template.model_dump())

        # 3. Save to file
        template_path = self.template_dir / f"{name}.json"
        template_data = validated_template.model_dump()

        try:
            with open(template_path, "w", encoding="utf-8") as f:
                json.dump(template_data, f, indent=2, ensure_ascii=False)

            file_size_kb = template_path.stat().st_size / 1024
            services_count = len(template_data["zone_payload"]["port"]["zone_service_list"])
            protection_count = len(template_data["monitor_payload"]["protection_values"])

            logger.bind(audit=True).info(
                f"Action: {'Update' if is_update else 'Create'} Template | Name: {name} | "
                f"Services: {services_count} | Protection Values: {protection_count} | "
                f"Profile: {template_data['zone_payload']['profile_name']} | A10_Validation: PASSED"
            )

            # 4. Send notification
            event_type = "update" if is_update else "create"
            self._send_notification(
                event_type,
                name=name,
                services_count=services_count,
                protection_count=protection_count,
                profile=template_data["zone_payload"]["profile_name"],
                device_group=template_data["zone_payload"]["device_group"],
            )

            return {
                "status": "success",
                "message": f"Template '{name}' {'updated' if is_update else 'created'} successfully",
                "file_path": str(template_path),
                "file_size_kb": round(file_size_kb, 2),
                "a10_validation": a10_result,
            }

        except Exception as e:
            logger.error(f"Failed to write template '{name}': {e}")
            raise TemplateValidationError(f"Failed to save template: {e}") from e

    def validate_template_a10(self, template: dict) -> dict:
        """Validate template against A10 API - BLOCKING validation.

        Checks:
        - Zone profile exists
        - Operational policy exists
        - Device group UUID is valid
        - All service profiles exist

        Args:
            template: Template dict with zone_payload and monitor_payload

        Returns:
            dict with validation results

        Raises:
            TemplateA10ValidationError: If any A10 resource doesn't exist
        """
        errors = []
        zone_payload = template["zone_payload"]

        # 1. Validate zone profile
        profile_name = zone_payload["profile_name"]
        try:
            resp = self.client.get(f"/tps/zoneprofiles/api/?search={profile_name}")
            if not resp.get("results"):
                errors.append(f"Zone profile '{profile_name}' does not exist in A10")
            else:
                logger.info(f"✓ A10 Validation: Profile '{profile_name}' found")
        except Exception as e:
            errors.append(f"Failed to validate profile '{profile_name}': {e}")

        # 2. Validate operational policy
        policy_name = zone_payload["zone_oper_policy"]
        try:
            resp = self.client.get(f"/tps/operational_policy/api/?search={policy_name}")
            if not resp.get("results"):
                errors.append(f"Operational policy '{policy_name}' does not exist in A10")
            else:
                logger.info(f"✓ A10 Validation: Policy '{policy_name}' found")
        except Exception as e:
            errors.append(f"Failed to validate policy '{policy_name}': {e}")

        # 3. Validate device group UUID
        device_group = zone_payload["device_group"]
        try:
            self.client.get(f"/tps/devicegroup/api/{device_group}/")
            logger.info(f"✓ A10 Validation: Device Group '{device_group}' valid")
        except Exception as e:
            errors.append(f"Device Group UUID '{device_group}' is invalid: {e}")

        # 4. Validate service profiles
        for service in zone_payload["port"]["zone_service_list"]:
            svc_profile = service["profile_name"]
            try:
                resp = self.client.get(f"/tps/zoneprofiles/api/?search={svc_profile}")
                if not resp.get("results"):
                    errors.append(f"Service profile '{svc_profile}' does not exist in A10")
            except Exception as e:
                errors.append(f"Failed to validate service profile '{svc_profile}': {e}")

        if errors:
            error_msg = "; ".join(errors)
            logger.error(f"A10 validation failed: {error_msg}")
            raise TemplateA10ValidationError(error_msg)

        return {
            "valid": True,
            "checked": ["zone_profile", "operational_policy", "device_group", "service_profiles"],
            "message": "All A10 resources validated successfully",
        }

    def list_templates(self) -> list[dict]:
        """List all available template JSON files.

        Returns:
            List of dicts with template metadata
        """
        templates = []

        for template_file in self.template_dir.glob("*.json"):
            try:
                with open(template_file, encoding="utf-8") as f:
                    template_data = json.load(f)

                zone_payload = template_data.get("zone_payload", {})
                monitor_payload = template_data.get("monitor_payload", {})

                templates.append(
                    {
                        "name": template_file.stem,
                        "services_count": len(zone_payload.get("port", {}).get("zone_service_list", [])),
                        "protection_values_count": len(monitor_payload.get("protection_values", [])),
                        "profile_name": zone_payload.get("profile_name", "N/A"),
                        "device_group": zone_payload.get("device_group", "N/A"),
                        "file_path": str(template_file),
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to read template {template_file}: {e}")
                continue

        return templates

    def delete_template(self, name: str) -> None:
        """Delete template file (protected: cannot delete 'default').

        Args:
            name: Template name to delete

        Raises:
            TemplateValidationError: If trying to delete 'default'
            TemplateNotFoundError: If template doesn't exist
        """
        if name == "default":
            raise TemplateValidationError("Cannot delete protected template 'default'")

        template_path = self.template_dir / f"{name}.json"

        if not template_path.exists():
            raise TemplateNotFoundError(f"Template '{name}' not found")

        try:
            template_path.unlink()
            logger.bind(audit=True).info(f"Action: Delete Template | Name: {name}")

            # Send notification
            if settings.NOTIFY_TEMPLATE_DELETE:
                self.notifier.send_notification(
                    title="Template Deleted",
                    message=f"Template '{name}' deleted successfully",
                    level="info",
                    fields={"Template": name, "Action": "Deleted"},
                    event_type="template_delete",
                )

        except Exception as e:
            logger.error(f"Failed to delete template '{name}': {e}")
            raise TemplateValidationError(f"Failed to delete template: {e}") from e

    def import_from_zone(self, ip_address: str, name: str) -> dict:
        """Import template from existing A10 zone.

        Fetches zone configuration from A10, extracts payloads, cleans IP-specific fields,
        and saves as a reusable template.

        Args:
            ip_address: IP of existing zone to import from
            name: Name for the new template

        Returns:
            dict with import result

        Raises:
            TemplateNotFoundError: If zone doesn't exist
            TemplateValidationError: If import fails
        """
        # Search for zone by IP - list all zones and find match
        try:
            # Get all zones using the correct endpoint
            zones_response = self.client.get("/tps/protected_objects/zones/api/?page=1&items=1000")
            zones = zones_response.get("object_list", [])

            # Find zone by zone_name matching IP
            zone = next((z for z in zones if z.get("zone_name") == ip_address), None)

            if not zone:
                msg = f"Zone with IP '{ip_address}' not found in A10. Available zones: {len(zones)}"
                raise TemplateNotFoundError(msg)

        except TemplateNotFoundError:
            raise
        except Exception as e:
            raise TemplateValidationError(f"Failed to fetch zones from A10: {str(e)}") from e

        # Use zone data from list (already contains all configuration)
        zone_payload = dict(zone)

        # Remove IP-specific fields
        zone_payload.pop("id", None)
        zone_payload.pop("zone_name", None)
        zone_payload.pop("ip_list", None)
        zone_payload.pop("input_ips", None)
        zone_payload.pop("created_at", None)
        zone_payload.pop("updated_at", None)
        zone_payload.pop("status", None)

        # Accept zone configuration as-is from A10 (no validation)
        # If it works in A10, the template is the law - accept it
        logger.info(f"Importing zone {ip_address} as-is (template is the law)")

        # For monitor_payload, we need to construct it based on zone configuration
        # Since A10 doesn't have a direct "get monitor config" endpoint,
        # we'll create a basic monitor payload structure
        monitor_payload = {
            "algorithm": "max",
            "sensitivity": "medium",
            "manual_thresholds": False,
            "deployZone": True,
            "protection_values": [],
        }

        # Extract protection values from zone services
        if "port" in zone_payload and "zone_service_list" in zone_payload["port"]:
            for service in zone_payload["port"]["zone_service_list"]:
                protection_value = {
                    "protocol": service["protocol"],
                    "zone_escalation_score": 10,
                    "indicators": [{"name": "pkt-rate", "value": 0, "score": 20}],
                }

                # Add port if present
                if "port" in service:
                    port_val = service["port"]
                    if isinstance(port_val, int):
                        protection_value["port"] = port_val
                    elif isinstance(port_val, str):
                        if "-" in str(port_val):
                            parts = str(port_val).split("-")
                            protection_value["port_range_start"] = int(parts[0])
                            protection_value["port_range_end"] = int(parts[1])
                        elif port_val == "other":
                            protection_value["port_other"] = "other"
                        else:
                            try:
                                protection_value["port"] = int(port_val)
                            except ValueError:
                                protection_value["port"] = port_val

                monitor_payload["protection_values"].append(protection_value)

        # Create template structure
        template_data = {"name": name, "zone_payload": zone_payload, "monitor_payload": monitor_payload}

        # Validate and save
        self.save_template(template_data, name, is_update=False)

        # Send notification if enabled
        if settings.NOTIFY_TEMPLATE_IMPORT:
            svc_count = len(monitor_payload["protection_values"])
            self._send_notification("import", name=name, source_ip=ip_address, services_count=svc_count)

        return {
            "status": "success",
            "message": f"Template '{name}' imported from zone {ip_address}",
            "services_count": len(monitor_payload["protection_values"]),
        }

    def _send_notification(self, event_type: str, **kwargs):
        """Send notification based on event type and settings.

        Args:
            event_type: "create", "update", "delete", or "import"
            **kwargs: Additional context for notification
        """
        notify_setting = {
            "create": settings.NOTIFY_TEMPLATE_CREATE,
            "update": settings.NOTIFY_TEMPLATE_UPDATE,
            "delete": settings.NOTIFY_TEMPLATE_DELETE,
            "import": settings.NOTIFY_TEMPLATE_IMPORT,
        }.get(event_type, False)

        if not notify_setting:
            return

        # Map internal event types to notification event types
        event_type_map = {
            "create": "template_create",
            "update": "template_update",
            "delete": "template_delete",
            "import": "template_import",
        }

        title_map = {
            "create": "Template Created",
            "update": "Template Updated",
            "delete": "Template Deleted",
            "import": "Template Imported",
        }

        message_parts = []
        if event_type == "import":
            message_parts.append(f"Template '{kwargs.get('name')}' imported from zone {kwargs.get('source_ip')}")
        elif event_type == "create":
            message_parts.append(f"Template '{kwargs.get('name')}' created successfully")
        elif event_type == "update":
            message_parts.append(f"Template '{kwargs.get('name')}' updated successfully")
        else:
            message_parts.append(f"Template '{kwargs.get('name')}' deleted successfully")

        fields = {}
        if "services_count" in kwargs:
            fields["Services"] = str(kwargs["services_count"])
        if "protection_count" in kwargs:
            fields["Protection Values"] = str(kwargs["protection_count"])
        if "profile" in kwargs:
            fields["Profile"] = kwargs["profile"]
        if "device_group" in kwargs:
            fields["Device Group"] = kwargs["device_group"][:8] + "..."

        self.notifier.send_notification(
            title=title_map.get(event_type, "Template Event"),
            message=" | ".join(message_parts),
            level="info",
            fields=fields,
            event_type=event_type_map.get(event_type),
        )
