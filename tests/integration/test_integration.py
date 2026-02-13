import os
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from a10_guardian.core.dependencies import get_a10_client, get_mitigation_service, verify_api_token
from a10_guardian.main import app
from a10_guardian.services.mitigation_service import MitigationService

mock_a10 = MagicMock()
mock_mitigation = MagicMock(spec=MitigationService)

app.dependency_overrides[get_a10_client] = lambda: mock_a10
app.dependency_overrides[get_mitigation_service] = lambda: mock_mitigation
app.dependency_overrides[verify_api_token] = lambda: True

client = TestClient(app)
AUTH_HEADERS = {"x-api-token": os.getenv("API_SECRET_TOKEN", "test-token")}


@pytest.fixture(autouse=True)
def reset_mock():
    mock_a10.reset_mock()
    mock_mitigation.reset_mock()
    mock_a10.connect.return_value = None


def test_health_check_upstream():
    response = client.get("/health?check_upstream=true")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["upstream"] == "connected"
    mock_a10.connect.assert_called_once()


def test_mitigate_ip():
    mock_mitigation.ensure_mitigation.return_value = {
        "status": "success",
        "message": "Mitigation started for 1.2.3.4",
    }

    response = client.post("/api/v1/mitigation/zones/mitigate/1.2.3.4")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_delete_zone():
    mock_resp = MagicMock()
    mock_resp.message = "Zone 5.6.7.8 removed successfully"
    mock_resp.status = "deleted"
    mock_resp.model_dump = lambda **_: {"message": "Zone 5.6.7.8 removed successfully", "status": "deleted"}
    mock_mitigation.remove_zone.return_value = mock_resp

    response = client.delete("/api/v1/mitigation/zones/remove/5.6.7.8")
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"
