from unittest.mock import patch

import pytest

from a10_guardian.services.notification_service import NotificationService


class TestNotificationService:
    @pytest.fixture
    def service(self):
        with patch("a10_guardian.services.notification_service.settings") as mock_settings:
            mock_settings.WEBHOOK_ENABLED = True
            mock_settings.WEBHOOK_URL = "http://fake-webhook"
            mock_settings.WEBHOOK_USERNAME = "A10 Guardian"
            mock_settings.WEBHOOK_EMOJI = ":shield:"
            mock_settings.WEBHOOK_FOOTER = "A10 Guardian API"
            mock_settings.TELEGRAM_BOT_TOKEN = None
            mock_settings.TELEGRAM_CHAT_ID = None
            yield NotificationService()

    def test_send_notification_success(self, service):
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.raise_for_status = lambda: None

            service.send_notification("Title", "Message", "info")

            mock_post.assert_called_once()
            _, kwargs = mock_post.call_args
            assert kwargs["json"]["attachments"][0]["title"].endswith("Title")
            assert kwargs["json"]["attachments"][0]["color"] == "#3498db"

    def test_send_notification_disabled(self):
        with patch("a10_guardian.services.notification_service.settings") as mock_settings:
            mock_settings.WEBHOOK_ENABLED = False
            mock_settings.WEBHOOK_URL = None
            mock_settings.WEBHOOK_USERNAME = "A10 Guardian"
            mock_settings.WEBHOOK_EMOJI = ":shield:"
            mock_settings.WEBHOOK_FOOTER = "A10 Guardian API"
            mock_settings.TELEGRAM_BOT_TOKEN = None
            mock_settings.TELEGRAM_CHAT_ID = None
            service = NotificationService()

            with patch("requests.post") as mock_post:
                service.send_notification("T", "M")
                mock_post.assert_not_called()

    def test_send_notification_error(self, service):
        with patch("requests.post", side_effect=Exception("Net Error")):
            with patch("a10_guardian.services.notification_service.logger.error") as mock_log:
                service.send_notification("T", "M")
                mock_log.assert_called_once()

    def test_send_telegram_notification_success(self):
        with patch("a10_guardian.services.notification_service.settings") as mock_settings:
            mock_settings.WEBHOOK_ENABLED = False
            mock_settings.WEBHOOK_URL = None
            mock_settings.WEBHOOK_USERNAME = "A10 Guardian"
            mock_settings.WEBHOOK_FOOTER = "A10 Guardian API"
            mock_settings.TELEGRAM_BOT_TOKEN = "fake-token"
            mock_settings.TELEGRAM_CHAT_ID = "123456"
            service = NotificationService()

            with patch("requests.post") as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.raise_for_status = lambda: None

                service.send_notification("Title", "Message", "info")

                mock_post.assert_called_once()
                args, kwargs = mock_post.call_args
                assert "api.telegram.org" in args[0]
                assert kwargs["json"]["chat_id"] == "123456"
                assert "Title" in kwargs["json"]["text"]

    def test_send_dual_channel_notification(self):
        with patch("a10_guardian.services.notification_service.settings") as mock_settings:
            mock_settings.WEBHOOK_ENABLED = True
            mock_settings.WEBHOOK_URL = "http://fake-webhook"
            mock_settings.WEBHOOK_USERNAME = "A10 Guardian"
            mock_settings.WEBHOOK_FOOTER = "A10 Guardian API"
            mock_settings.TELEGRAM_BOT_TOKEN = "fake-token"
            mock_settings.TELEGRAM_CHAT_ID = "123456"
            service = NotificationService()

            with patch("requests.post") as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.raise_for_status = lambda: None

                service.send_notification("Title", "Message", "info")

                assert mock_post.call_count == 2
                # First call should be Telegram
                telegram_call = mock_post.call_args_list[0]
                assert "api.telegram.org" in telegram_call[0][0]
                # Second call should be webhook
                webhook_call = mock_post.call_args_list[1]
                assert webhook_call[0][0] == "http://fake-webhook"
