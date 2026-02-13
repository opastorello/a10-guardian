import sys
from unittest.mock import MagicMock, patch

import pytest

# Ensure we are patching a fresh import
if "a10_guardian.mcp_server" in sys.modules:
    del sys.modules["a10_guardian.mcp_server"]

# We need to mock FastMCP before importing the module
with patch("fastmcp.FastMCP") as MockFastMCP:
    instance = MockFastMCP.return_value

    def decorator_factory(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

    instance.tool.side_effect = decorator_factory
    instance.resource.side_effect = decorator_factory
    instance.prompt.side_effect = decorator_factory
    instance._additional_http_routes = []

    with patch("a10_guardian.core.client.A10Client"):
        from a10_guardian import mcp_server


class TestMcpIntegration:
    @pytest.fixture(autouse=True)
    def mock_container(self):
        self.mock_system_svc = MagicMock()
        self.mock_mit_svc = MagicMock()
        with (
            patch.object(mcp_server.Container, "get_system_service", return_value=self.mock_system_svc),
            patch.object(mcp_server.Container, "get_mitigation_service", return_value=self.mock_mit_svc),
        ):
            yield

    def test_get_system_health_success(self):
        self.mock_system_svc.get_info.return_value = {
            "hostname": "box1",
            "uptime": "10h",
            "agalaxy_version": "5.0",
            "product_name": "TPS",
        }

        result = mcp_server.get_system_health()
        assert "System Online" in result
        assert "box1" in result

    def test_get_system_health_error(self):
        self.mock_system_svc.get_info.side_effect = Exception("Fail")

        result = mcp_server.get_system_health()
        assert "Error checking health" in result

    def test_list_active_mitigations_found(self):
        self.mock_mit_svc.list_zones.return_value = {
            "total": 1,
            "zones": [{"zone_name": "1.1.1.1", "operational_mode": "monitor"}],
        }

        result = mcp_server.list_active_mitigations()
        assert "Found 1 active mitigations" in result
        assert "1.1.1.1" in result

    def test_list_active_mitigations_empty(self):
        self.mock_mit_svc.list_zones.return_value = {"total": 0, "zones": []}

        result = mcp_server.list_active_mitigations()
        assert "No active mitigations found" in result

    def test_mitigate_ip_success(self):
        self.mock_mit_svc.ensure_mitigation.return_value = {
            "status": "success",
            "message": "Started mitigation for 1.2.3.4",
        }

        result = mcp_server.mitigate_ip("1.2.3.4")
        assert "Started mitigation" in result

    def test_mitigate_ip_error(self):
        self.mock_mit_svc.ensure_mitigation.side_effect = Exception("Connection failed")

        result = mcp_server.mitigate_ip("1.2.3.4")
        assert "Error executing mitigation" in result

    def test_remove_mitigation_success(self):
        mock_resp = MagicMock()
        mock_resp.message = "Zone removed"
        self.mock_mit_svc.remove_zone.return_value = mock_resp

        result = mcp_server.remove_mitigation("1.2.3.4")
        assert "Zone removed" in result

    def test_get_zone_status_found(self):
        self.mock_mit_svc.get_zone_status.return_value = {
            "zone_name": "1.2.3.4",
            "zone_id": "abc-123",
            "operational_mode": "monitor",
            "services_count": 5,
            "ip_list": ["1.2.3.4"],
        }

        result = mcp_server.get_zone_status("1.2.3.4")
        assert "1.2.3.4" in result
        assert "monitor" in result

    def test_get_zone_status_not_found(self):
        self.mock_mit_svc.get_zone_status.return_value = None

        result = mcp_server.get_zone_status("9.9.9.9")
        assert "No zone found" in result
