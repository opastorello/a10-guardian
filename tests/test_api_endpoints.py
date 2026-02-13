from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from a10_guardian.core.dependencies import get_mitigation_service, get_system_service, verify_api_token
from a10_guardian.main import app
from a10_guardian.services.mitigation_service import MitigationService
from a10_guardian.services.system_service import SystemService


class TestApiEndpoints:
    @pytest.fixture
    def mock_mitigation_service(self):
        return MagicMock(spec=MitigationService)

    @pytest.fixture
    def mock_system_service(self):
        return MagicMock(spec=SystemService)

    @pytest.fixture
    def client(self, mock_mitigation_service, mock_system_service):
        app.dependency_overrides[get_mitigation_service] = lambda: mock_mitigation_service
        app.dependency_overrides[get_system_service] = lambda: mock_system_service
        app.dependency_overrides[verify_api_token] = lambda: True

        with TestClient(app) as c:
            yield c

        app.dependency_overrides = {}

    # --- Mitigation Tests ---

    def test_mitigate_ip(self, client, mock_mitigation_service):
        mock_mitigation_service.ensure_mitigation.return_value = {
            "status": "success",
            "message": "Mitigation started",
        }
        response = client.post("/api/v1/mitigation/zones/mitigate/1.2.3.4")
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_get_zone_status_found(self, client, mock_mitigation_service):
        mock_mitigation_service.get_zone_status.return_value = {
            "zone_name": "1.2.3.4",
            "zone_id": "abc-123",
            "operational_mode": "monitor",
            "services_count": 5,
            "ip_list": ["1.2.3.4"],
        }
        response = client.get("/api/v1/mitigation/zones/status/1.2.3.4")
        assert response.status_code == 200
        assert response.json()["zone_name"] == "1.2.3.4"

    def test_get_zone_status_not_found(self, client, mock_mitigation_service):
        mock_mitigation_service.get_zone_status.return_value = None
        response = client.get("/api/v1/mitigation/zones/status/9.9.9.9")
        assert response.status_code == 404

    def test_remove_zone(self, client, mock_mitigation_service):
        mock_resp = MagicMock()
        mock_resp.message = "deleted"
        mock_resp.status = "deleted"
        mock_resp.model_dump = lambda **_: {"message": "deleted", "status": "deleted"}
        mock_mitigation_service.remove_zone.return_value = mock_resp
        response = client.delete("/api/v1/mitigation/zones/remove/1.2.3.4")
        assert response.status_code == 200

    def test_list_zones(self, client, mock_mitigation_service):
        mock_mitigation_service.list_zones.return_value = {
            "total": 0,
            "page": 1,
            "items": 40,
            "zones": [],
        }
        response = client.get("/api/v1/mitigation/zones/list")
        assert response.status_code == 200

    def test_mitigation_error_handling(self, client, mock_mitigation_service):
        mock_mitigation_service.ensure_mitigation.side_effect = Exception("Boom")
        response = client.post("/api/v1/mitigation/zones/mitigate/1.2.3.4")
        assert response.status_code == 500

    # --- System Tests ---

    def test_get_system_info(self, client, mock_system_service):
        mock_system_service.get_info.return_value = {
            "hostname": "test-box",
            "uptime": "1d",
            "product_name": "TPS",
            "agalaxy_version": "5.0",
            "serial_number": "123",
        }
        response = client.get("/api/v1/system/info")
        assert response.status_code == 200
        assert response.json()["hostname"] == "test-box"

    def test_get_devices(self, client, mock_system_service):
        mock_system_service.get_devices.return_value = {"total": 0, "object_list": [], "page": 1}
        response = client.get("/api/v1/system/devices")
        assert response.status_code == 200

    def test_get_license(self, client, mock_system_service):
        mock_system_service.get_license.return_value = {"license_type": "Production"}
        response = client.get("/api/v1/system/license")
        assert response.status_code == 200

    def test_system_error_handling(self, client, mock_system_service):
        mock_system_service.get_info.side_effect = Exception("System Fail")
        response = client.get("/api/v1/system/info")
        assert response.status_code == 500
