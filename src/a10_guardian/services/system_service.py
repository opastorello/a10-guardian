from a10_guardian.core.client import A10Client


class SystemService:
    """Service for retrieving system health, status, and hardware information.

    Args:
        client (A10Client): Authenticated A10 client.
    """

    def __init__(self, client: A10Client):
        self.client = client

    def get_info(self) -> dict:
        """Retrieves general system information (Hostname, Uptime, Version).

        Flattens the nested platform object into top-level fields.

        Returns:
            dict: System details matching SystemInfoResponse.
        """
        raw = self.client.get("/dashboard/info/")
        platform = raw.get("platform", {}) or {}
        return {
            "hostname": raw.get("hostname"),
            "uptime": raw.get("uptime"),
            "product_name": platform.get("product_name") or raw.get("product_name"),
            "agalaxy_version": platform.get("agalaxy_version") or raw.get("agalaxy_version"),
            "serial_number": platform.get("serial_number") or raw.get("serial_number"),
        }

    def get_devices(self):
        """Lists all devices in the inventory (vThunder/Hardware).

        Returns:
            dict: List of devices.
        """
        return self.client.get("/inventory/device_list/json/", params={"get_all": "true"})

    def get_license(self) -> dict:
        """Retrieves license information.

        Returns:
            dict: License type, limits, and expiration.
        """
        response = self.client.get("/system/license/get_license/")
        return response.get("license", {})
