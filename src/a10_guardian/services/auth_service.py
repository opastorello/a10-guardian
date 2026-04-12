import base64
import json
import os
import re

import requests
import urllib3
from cryptography.fernet import Fernet, InvalidToken
from loguru import logger

from a10_guardian.core.config import settings

# Suppress SSL warnings
if not settings.A10_VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _get_fernet() -> Fernet | None:
    """Return a Fernet cipher keyed from API_SECRET_TOKEN, or None if unavailable."""
    try:
        # Derive a 32-byte URL-safe base64 key from the secret token
        raw = settings.API_SECRET_TOKEN.encode()[:32].ljust(32, b"\x00")
        key = base64.urlsafe_b64encode(raw)
        return Fernet(key)
    except Exception:
        return None


class AuthService:
    """Service responsible for authenticating with the A10 device.

    Handles login flow, session caching, and session validation.
    """

    def __init__(self):
        self.login_url = f"{settings.A10_BASE_URL}/auth/login/"
        self.cache_file = settings.SESSION_CACHE_FILE

    def save_session(self, session):
        """Saves the session cookies to an encrypted file.

        Uses Fernet (AES-128-CBC + HMAC-SHA256) keyed from API_SECRET_TOKEN.
        Falls back to plaintext only if encryption is unavailable.

        Args:
            session (requests.Session): The active session object.
        """
        try:
            # Ensure directory exists
            cache_dir = os.path.dirname(self.cache_file)
            if cache_dir:
                os.makedirs(cache_dir, exist_ok=True)

            payload = json.dumps(session.cookies.get_dict()).encode()
            fernet = _get_fernet()

            if fernet:
                data = fernet.encrypt(payload)
                with open(self.cache_file, "wb") as f:
                    f.write(data)
            else:
                logger.warning("Fernet unavailable — session cache written as plaintext")
                with open(self.cache_file, "w") as f:
                    f.write(payload.decode())

            # Restrict file to owner read/write only (effective on Linux/macOS)
            try:
                os.chmod(self.cache_file, 0o600)
            except OSError:
                pass  # Windows does not support POSIX chmod — acceptable

            logger.info(f"Session cached (encrypted) to {self.cache_file}")
        except Exception as e:
            logger.error(f"Failed to save session cache: {e}")

    def load_session(self):
        """Loads a session from the encrypted cache file if it exists.

        Returns:
            requests.Session: Restored session with cookies, or None if failed/missing.
        """
        if not os.path.exists(self.cache_file):
            return None

        try:
            fernet = _get_fernet()
            with open(self.cache_file, "rb") as f:
                raw = f.read()

            if fernet:
                try:
                    payload = fernet.decrypt(raw)
                    cookies = json.loads(payload)
                except (InvalidToken, Exception):
                    # Cache may be plaintext from a previous version — try direct parse
                    try:
                        cookies = json.loads(raw)
                        logger.warning("Session cache was plaintext — will be re-encrypted on next save")
                    except Exception:
                        logger.error("Session cache is corrupt or tampered — discarding")
                        self.invalidate_session()
                        return None
            else:
                cookies = json.loads(raw)

            session = requests.Session()
            session.cookies.update(cookies)

            # Restore common headers
            session.headers.update(
                {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                        " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    )
                }
            )
            logger.info(f"Loaded session from {self.cache_file}")
            return session
        except Exception as e:
            logger.error(f"Failed to load session cache: {e}")
            return None

    def validate_session(self, session):
        """Checks if the current session is still valid by probing the dashboard.

        Args:
            session (requests.Session): The session to validate.

        Returns:
            bool: True if valid, False if expired or invalid.
        """
        check_url = f"{settings.A10_BASE_URL}/dashboard/"

        logger.debug("Validating cached session...")
        try:
            response = session.get(check_url, verify=settings.A10_VERIFY_SSL, timeout=10, allow_redirects=False)
            if response.status_code == 200:
                logger.debug("Session is valid.")
                return True
            else:
                # Any non-200 (302 to logout, login, or anything else) means session is expired
                location = response.headers.get("Location", "")
                logger.warning(f"Cached session expired (status={response.status_code}, location={location})")
                return False

        except requests.RequestException:
            logger.error("Network error verifying session.")
            return False

    def login(self, username, password):
        """Performs a full login flow, scraping CSRF tokens and handling redirects.

        Args:
            username (str): A10 username.
            password (str): A10 password.

        Returns:
            requests.Session: Authenticated session if successful, None otherwise.
        """
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            }
        )

        logger.info(f"Accessing login page: {self.login_url}")
        try:
            response = session.get(self.login_url, verify=settings.A10_VERIFY_SSL, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Error accessing page: {e}")

            return None

        # Handle single or double quotes
        csrf_match = re.search(r"name=['\"]csrfmiddlewaretoken['\"] value=['\"]([^'\"]+)['\"]", response.text)
        if not csrf_match:
            logger.error("Could not find csrfmiddlewaretoken in response.")

            return None

        csrf_token = csrf_match.group(1)

        region_match = re.search(r'name="region" value="([^"]+)"', response.text)
        region = region_match.group(1) if region_match else "http://127.0.0.1:5000/v3"

        payload = {"csrfmiddlewaretoken": csrf_token, "username": username, "password": password, "region": region}

        headers = {"Referer": self.login_url}

        logger.info(f"Attempting login for user: {username}")
        try:
            post_response = session.post(
                self.login_url, data=payload, headers=headers, verify=settings.A10_VERIFY_SSL, timeout=10
            )
            post_response.raise_for_status()

            if post_response.url != self.login_url and "login" not in post_response.url:
                logger.info(f"Login successful! Redirected to: {post_response.url}")
                self.save_session(session)

                return session

            if "id_username" in post_response.text:
                logger.error("Login failed. Still on login page.")

                return None

            return session

        except requests.RequestException as e:
            logger.error(f"Error during login POST: {e}")

            return None

    def get_authenticated_session(self, username, password):
        """Retrieves a valid session, either from cache or by performing a new login.

        Args:
            username (str): A10 username.
            password (str): A10 password.

        Returns:
            requests.Session: Authenticated session object.
        """
        session = self.load_session()
        if session and self.validate_session(session):
            return session

        logger.info("Performing full login...")
        return self.login(username, password)

    def invalidate_session(self):
        """Removes the cached session file."""
        if os.path.exists(self.cache_file):
            try:
                os.remove(self.cache_file)
                logger.info("Session cache file removed.")
            except Exception as e:
                logger.error(f"Failed to remove session cache: {e}")
