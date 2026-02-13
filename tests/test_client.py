from unittest.mock import MagicMock, patch

import pytest
import requests

from a10_guardian.core.client import A10Client


class TestA10Client:
    @pytest.fixture
    def mock_auth_service(self):
        with patch("a10_guardian.core.client.AuthService") as MockAuth:
            yield MockAuth.return_value

    @pytest.fixture
    def mock_session(self):
        session = MagicMock(spec=requests.Session)
        session.cookies = {"csrftoken": "test-csrf"}
        session.mount = MagicMock()
        return session

    @pytest.fixture
    def client(self, mock_auth_service, mock_session):
        mock_auth_service.get_authenticated_session.return_value = mock_session
        c = A10Client("user", "pass")
        return c

    def test_connect_success(self, client, mock_auth_service, mock_session):
        client.connect()
        assert client.session == mock_session
        mock_auth_service.get_authenticated_session.assert_called_with("user", "pass")

    def test_connect_fail(self, client, mock_auth_service):
        mock_auth_service.get_authenticated_session.return_value = None
        with pytest.raises(ConnectionError, match="Failed to authenticate"):
            client.connect()

    def test_get_request_success(self, client, mock_session):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://test/endpoint"
        mock_response.json.return_value = {"key": "value"}
        mock_session.request.return_value = mock_response

        result = client.get("/endpoint")
        assert result == {"key": "value"}
        mock_session.request.assert_called_once()

    def test_post_request_with_csrf(self, client, mock_session):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://test/create"
        mock_response.json.return_value = {"status": "ok"}
        mock_session.request.return_value = mock_response

        client.post("/create", json_data={"a": 1})

        _, kwargs = mock_session.request.call_args
        headers = kwargs["headers"]
        assert headers["X-Csrftoken"] == "test-csrf"
        assert headers["Content-Type"] == "application/json"
        assert headers["X-Requested-With"] == "XMLHttpRequest"

    def test_request_session_expired_retry(self, client, mock_session, mock_auth_service):
        response_403 = MagicMock()
        response_403.status_code = 403
        response_403.url = "https://test/retry"

        response_200 = MagicMock()
        response_200.status_code = 200
        response_200.url = "https://test/retry"
        response_200.json.return_value = {"retry": "success"}

        mock_session.request.side_effect = [response_403, response_200]

        result = client.get("/retry")

        assert result == {"retry": "success"}
        assert mock_session.request.call_count == 2

    def test_request_exception_propagation(self, client, mock_session):
        error = requests.RequestException("Network Error")
        error.response = None
        mock_session.request.side_effect = error

        with pytest.raises(requests.RequestException):
            client.get("/fail")

    def test_invalidate_session(self, client, mock_auth_service):
        client.invalidate_session()
        assert client.session is None
        mock_auth_service.invalidate_session.assert_called_once()
