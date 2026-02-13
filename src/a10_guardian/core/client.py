from typing import Any

import requests
from loguru import logger
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from a10_guardian.core.config import settings
from a10_guardian.services.auth_service import AuthService


class A10Client:
    """HTTP Client for communicating with the A10 Thunder TPS API.

    Handles authentication, session management, CSRF tokens, and request retries.

    Args:
        username (str): A10 admin username.
        password (str): A10 admin password.
    """

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.auth_service = AuthService()
        self.session: requests.Session | None = None

    def connect(self):
        """Authenticates with the A10 device and establishes a session.

        Raises:
            Exception: If authentication fails.
        """
        logger.debug(f"Connecting to A10 as user: {self.username}")
        self.session = self.auth_service.get_authenticated_session(self.username, self.password)
        if not self.session:
            raise ConnectionError("Failed to authenticate with A10.")

        # Mount a standard retry adapter for network-level glitches (not auth)
        # This handles 500, 502, 503, 504 automatically
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        self.session.mount("http://", HTTPAdapter(max_retries=retries))

    def _ensure_connection(self):
        """Checks if a session exists, attempting to connect if not."""
        if not self.session:
            self.connect()

    def _request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        """Executes an HTTP request to the A10 API.

        Handles common logic like URL construction, SSL verification,
        CSRF header injection for state-changing methods, and session renewal.

        Args:
            method (str): HTTP method (GET, POST, DELETE, etc.).
            endpoint (str): API endpoint path (e.g., '/tps/zones').
            **kwargs: Additional arguments passed to requests.Session methods.

        Returns:
            dict: The JSON response from the API.

        Raises:
            requests.HTTPError: If the API returns a non-200 status.
        """
        self._ensure_connection()
        url = f"{settings.A10_BASE_URL}{endpoint}"

        # Merge default settings with kwargs
        kwargs.setdefault("verify", settings.A10_VERIFY_SSL)
        kwargs.setdefault("timeout", 20)  # Increased timeout slightly

        # Handle CSRF for state-changing methods
        if method.upper() in ["POST", "DELETE", "PUT", "PATCH"]:
            self._inject_csrf_token(kwargs)

        try:
            response = self.session.request(method, url, **kwargs)

            # Check for soft-errors (redirects to login or 403)
            if self._is_session_expired(response):
                logger.warning(f"Session expired (Status: {response.status_code}). Re-authenticating...")
                self.connect()

                # Re-inject CSRF for the retry
                if method.upper() in ["POST", "DELETE", "PUT", "PATCH"]:
                    self._inject_csrf_token(kwargs)

                response = self.session.request(method, url, **kwargs)

            response.raise_for_status()

            # Handle 204 No Content
            if response.status_code == 204:
                return {}

            return response.json()

        except requests.RequestException as e:
            self._log_error(method, url, e)
            raise

    def _inject_csrf_token(self, kwargs: dict):
        """Injects CSRF headers into the request kwargs."""
        csrf_token = self.session.cookies.get("csrftoken")
        headers = kwargs.get("headers", {})
        if csrf_token:
            headers.update(
                {
                    "X-Csrftoken": csrf_token,
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                    "Origin": settings.A10_BASE_URL,
                    "Referer": f"{settings.A10_BASE_URL}/",
                }
            )
        else:
            logger.warning("CSRF token not found in cookies for state-changing request.")
        kwargs["headers"] = headers

    def _is_session_expired(self, response: requests.Response) -> bool:
        """Determines if the session has expired based on the response."""
        return response.status_code == 403 or (response.status_code == 200 and "login" in response.url)

    def _log_error(self, method: str, url: str, e: requests.RequestException):
        """Logs detailed error information."""
        if e.response is not None:
            logger.error(
                f"API {method.upper()} Request Failed: {url} | "
                f"Status: {e.response.status_code} | Body: {e.response.text}"
            )
        else:
            logger.error(f"API {method.upper()} Request Failed: {url} | Error: {e}")

    def get(self, endpoint: str, params: dict | None = None) -> dict[str, Any]:
        return self._request("GET", endpoint, params=params)

    def post(self, endpoint: str, json_data: dict | None = None) -> dict[str, Any]:
        return self._request("POST", endpoint, json=json_data)

    def delete(self, endpoint: str, json_data: dict | None = None) -> dict[str, Any]:
        return self._request("DELETE", endpoint, json=json_data)

    def invalidate_session(self):
        """Invalidates the current session locally and clears the cache."""
        self.session = None
        self.auth_service.invalidate_session()
