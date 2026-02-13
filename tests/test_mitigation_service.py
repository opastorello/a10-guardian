from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from a10_guardian.core.client import A10Client
from a10_guardian.services.mitigation_service import MitigationService
from a10_guardian.services.notification_service import NotificationService


class TestMitigationService:
    @pytest.fixture
    def mock_client(self):
        return MagicMock(spec=A10Client)

    @pytest.fixture
    def mock_notifier(self):
        return MagicMock(spec=NotificationService)

    @pytest.fixture
    def mitigation_service(self, mock_client, mock_notifier):
        return MitigationService(client=mock_client, notifier=mock_notifier)

    def test_get_zone_by_ip_found(self, mitigation_service, mock_client):
        mock_client.get.return_value = {
            "object_list": [{"zone_name": "1.2.3.4", "id": "id_1"}, {"zone_name": "5.6.7.8", "id": "id_2"}]
        }

        result = mitigation_service.get_zone_by_ip("5.6.7.8")
        assert result["id"] == "id_2"

    def test_get_zone_by_ip_not_found(self, mitigation_service, mock_client):
        mock_client.get.return_value = {"object_list": []}
        result = mitigation_service.get_zone_by_ip("9.9.9.9")
        assert result is None

    def test_create_zone_raw(self, mitigation_service, mock_client, mock_notifier):
        payload = {"zone_name": "1.1.1.1", "ip_list": ["1.1.1.1"], "input_ips": ["1.1.1.1"]}
        mock_client.post.return_value = {"status": "ok", "id": "new-id"}

        with patch("a10_guardian.services.mitigation_service.logger"):
            mitigation_service.create_zone_raw(payload)
            mock_client.post.assert_called_once()

    def test_remove_zone_success(self, mitigation_service, mock_client, mock_notifier):
        with patch.object(mitigation_service, "get_zone_by_ip", return_value={"id": "abc", "zone_name": "1.2.3.4"}):
            mock_client.delete.return_value = {"status": "deleted"}

            resp = mitigation_service.remove_zone("1.2.3.4")
            assert resp.status == "deleted"

            mock_notifier.send_notification.assert_called_once()
            _, kwargs = mock_notifier.send_notification.call_args
            assert "Stopped" in kwargs["title"]

    def test_remove_zone_not_found(self, mitigation_service):
        with patch.object(mitigation_service, "get_zone_by_ip", return_value=None):
            with pytest.raises(HTTPException) as exc:
                mitigation_service.remove_zone("1.2.3.4")
            assert exc.value.status_code == 404

    def test_start_monitoring(self, mitigation_service, mock_client):
        config = {"algorithm": "heuristic", "deployZone": True}
        mitigation_service.start_monitoring("zone_123", config)

        mock_client.post.assert_called_with("/tps/protected_objects/zones/api/zone_123/monitor/", json_data=config)

    def test_list_zones(self, mitigation_service, mock_client):
        mock_client.get.return_value = {
            "total": 2,
            "object_list": [
                {"zone_name": "1.1.1.1", "id": "id1", "operational_mode": "monitor"},
                {"zone_name": "2.2.2.2", "id": "id2", "operational_mode": "idle"},
            ],
        }
        result = mitigation_service.list_zones(page=1, items=40)
        assert result["total"] == 2
        assert len(result["zones"]) == 2
        assert result["zones"][0]["zone_name"] == "1.1.1.1"
