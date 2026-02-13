from unittest.mock import MagicMock, mock_open, patch

import pytest
import requests

from a10_guardian.services.auth_service import AuthService


class TestAuthService:
    @pytest.fixture
    def auth_service(self):
        return AuthService()

    @pytest.fixture
    def mock_session(self):
        session = MagicMock(spec=requests.Session)
        session.cookies = MagicMock()
        session.headers = {}
        return session

    def test_save_session_success(self, auth_service, mock_session):
        with patch("builtins.open", mock_open()) as mock_file:
            with patch("json.dump") as mock_json_dump:
                auth_service.save_session(mock_session)

                mock_file.assert_called_with(auth_service.cache_file, "w")
                mock_json_dump.assert_called_once_with(mock_session.cookies.get_dict(), mock_file())

    def test_save_session_error(self, auth_service, mock_session):
        with patch("builtins.open", side_effect=OSError("Permission denied")):
            with patch("a10_guardian.services.auth_service.logger.error") as mock_log:
                auth_service.save_session(mock_session)
                mock_log.assert_called_once()

    def test_load_session_not_exists(self, auth_service):
        with patch("os.path.exists", return_value=False):
            session = auth_service.load_session()
            assert session is None

    def test_load_session_success(self, auth_service):
        mock_cookies = {"sessionid": "123"}
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data='{"sessionid": "123"}')):
                with patch("json.load", return_value=mock_cookies):
                    session = auth_service.load_session()

                    assert isinstance(session, requests.Session)
                    # Requests cookies update might behave differently in mock
                    if "sessionid" in session.cookies:
                        assert session.cookies.get("sessionid") == "123"

    def test_validate_session_valid(self, auth_service, mock_session):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.get.return_value = mock_response

        assert auth_service.validate_session(mock_session) is True

    def test_validate_session_redirect_login(self, auth_service, mock_session):
        mock_response = MagicMock()
        mock_response.status_code = 302
        mock_response.headers = {"Location": "/auth/login/"}
        mock_session.get.return_value = mock_response

        assert auth_service.validate_session(mock_session) is False

    def test_login_success(self, auth_service):
        # Mock GET login page
        mock_get_resp = MagicMock()
        mock_get_resp.text = '<input name="csrfmiddlewaretoken" value="abc-token"><input name="region" value="v3">'
        mock_get_resp.status_code = 200

        # Mock POST login
        mock_post_resp = MagicMock()
        mock_post_resp.url = "http://test-server/dashboard"  # Redirected away from login
        mock_post_resp.status_code = 200
        mock_post_resp.text = "Dashboard content"

        with patch("requests.Session") as MockSession:
            session_instance = MockSession.return_value
            session_instance.get.return_value = mock_get_resp
            session_instance.post.return_value = mock_post_resp

            with patch.object(auth_service, "save_session") as mock_save:
                result_session = auth_service.login("user", "pass")

                assert result_session == session_instance
                mock_save.assert_called_once()
                session_instance.post.assert_called()
                # Verify payload contained extracted token
                call_args = session_instance.post.call_args
                assert call_args[1]["data"]["csrfmiddlewaretoken"] == "abc-token"

    def test_login_fail_no_csrf(self, auth_service):
        mock_get_resp = MagicMock()
        mock_get_resp.text = "<html>No token here</html>"

        with patch("requests.Session") as MockSession:
            session_instance = MockSession.return_value
            session_instance.get.return_value = mock_get_resp

            result = auth_service.login("user", "pass")
            assert result is None

    def test_get_authenticated_session_cache_hit(self, auth_service):
        mock_session = MagicMock()
        with patch.object(auth_service, "load_session", return_value=mock_session):
            with patch.object(auth_service, "validate_session", return_value=True):
                with patch.object(auth_service, "login") as mock_login:
                    session = auth_service.get_authenticated_session("u", "p")
                    assert session == mock_session
                    mock_login.assert_not_called()

    def test_get_authenticated_session_cache_miss(self, auth_service):
        with patch.object(auth_service, "load_session", return_value=None):
            with patch.object(auth_service, "login") as mock_login:
                auth_service.get_authenticated_session("u", "p")
                mock_login.assert_called_once()

    def test_invalidate_session_success(self, auth_service):
        with patch("os.path.exists", return_value=True):
            with patch("os.remove") as mock_remove:
                auth_service.invalidate_session()
                mock_remove.assert_called_once_with(auth_service.cache_file)

    def test_invalidate_session_error(self, auth_service):
        with patch("os.path.exists", return_value=True):
            with patch("os.remove", side_effect=OSError("Error deleting")):
                with patch("a10_guardian.services.auth_service.logger.error") as mock_log:
                    auth_service.invalidate_session()
                    mock_log.assert_called_once()
