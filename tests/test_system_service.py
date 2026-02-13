from unittest.mock import MagicMock

import pytest

from a10_guardian.core.client import A10Client
from a10_guardian.services.system_service import SystemService


class TestSystemService:
    @pytest.fixture
    def mock_client(self):
        return MagicMock(spec=A10Client)

    @pytest.fixture
    def system_service(self, mock_client):
        return SystemService(client=mock_client)

    def test_get_info(self, system_service, mock_client):
        mock_client.get.return_value = {
            "hostname": "box1",
            "uptime": "10d",
            "platform": {
                "product_name": "Thunder TPS",
                "agalaxy_version": "5.2.1",
                "serial_number": "SN123",
            },
        }

        result = system_service.get_info()
        assert result["hostname"] == "box1"
        assert result["uptime"] == "10d"
        assert result["product_name"] == "Thunder TPS"
        assert result["serial_number"] == "SN123"
        mock_client.get.assert_called_with("/dashboard/info/")

    def test_get_info_flat_response(self, system_service, mock_client):
        mock_client.get.return_value = {
            "hostname": "box2",
            "uptime": "1d",
            "product_name": "vThunder",
            "agalaxy_version": "5.0",
            "serial_number": "SN456",
        }

        result = system_service.get_info()
        assert result["hostname"] == "box2"
        assert result["product_name"] == "vThunder"

    def test_get_devices(self, system_service, mock_client):
        expected = {"total": 1, "object_list": []}
        mock_client.get.return_value = expected

        result = system_service.get_devices()
        assert result == expected
        mock_client.get.assert_called_with("/inventory/device_list/json/", params={"get_all": "true"})

    def test_get_license(self, system_service, mock_client):
        mock_response = {"license": {"license_type": "Production", "max_devices": 10}}
        mock_client.get.return_value = mock_response

        result = system_service.get_license()
        assert result["license_type"] == "Production"
        mock_client.get.assert_called_with("/system/license/get_license/")

    def test_get_license_empty(self, system_service, mock_client):
        mock_client.get.return_value = {}
        result = system_service.get_license()
        assert result == {}
