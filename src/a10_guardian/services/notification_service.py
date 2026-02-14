from datetime import datetime, timezone

import requests
from loguru import logger

from a10_guardian.core.config import settings

FIELD_ICONS = {
    "IP": "\U0001f310",
    "Zone ID": "\U0001f4ce",
    "Mode": "\u2699\ufe0f",
    "Services": "\U0001f6e1\ufe0f",
    "Profile": "\U0001f4cb",
}


class NotificationService:
    """Service to send notifications to external webhooks (Slack, Discord, Telegram)."""

    # Color mapping: Verde, Azul, Amarelo, Vermelho
    LEVEL_CONFIG = {
        "info": {"color": 0x3498DB, "icon": "\U0001f4a1"},  # Azul - 💡
        "warning": {"color": 0xFFA500, "icon": "\u26a0\ufe0f"},  # Laranja - ⚠️
        "error": {"color": 0xFF0000, "icon": "\u274c"},  # Vermelho - ❌
        "success": {"color": 0x00FF00, "icon": "\u2705"},  # Verde - ✅
    }

    # Event-specific emojis (override level icon)
    EVENT_EMOJIS = {
        "template_create": "\U0001f4cb",  # 📋
        "template_update": "\U0001f504",  # 🔄
        "template_delete": "\U0001f5d1\ufe0f",  # 🗑️
        "template_import": "\U0001f4e5",  # 📥
        "mitigation_start": "\U0001f6e1\ufe0f",  # 🛡️
        "mitigation_stop": "\u26d4",  # ⛔
        "a10_offline": "\u274c",  # ❌
        "a10_recovered": "\u2705",  # ✅
        "attack_detected": "\U0001f6a8",  # 🚨 Red alert siren
        "attack_mitigated": "\u2705",  # ✅ Green check (attack ended)
        "attack_ongoing": "\u26a0\ufe0f",  # ⚠️ Warning (long-running attack)
    }

    def __init__(self):
        self.url = settings.WEBHOOK_URL
        self.username = settings.WEBHOOK_USERNAME
        self.footer = settings.WEBHOOK_FOOTER
        # Telegram-specific settings
        self.telegram_bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
        self.telegram_chat_id = getattr(settings, "TELEGRAM_CHAT_ID", None)
        # Service is enabled if webhook OR telegram is configured
        self.enabled = (
            settings.WEBHOOK_ENABLED and self.url
        ) or (self.telegram_bot_token and self.telegram_chat_id)

    def send_notification(
        self,
        title: str,
        message: str,
        level: str = "info",
        fields: dict[str, str] | None = None,
        event_type: str | None = None,
    ):
        """Sends a structured notification to the configured webhook.

        Auto-detects Discord, Slack, or Telegram based on the webhook URL.

        Args:
            title: Title of the event.
            message: Detailed description.
            level: Severity (info, warning, error, success) - determines color.
            fields: Optional key-value pairs shown as structured fields.
            event_type: Optional event type for specific emoji (template_create, mitigation_start, etc).
        """
        if not self.enabled:
            return

        cfg = self.LEVEL_CONFIG.get(level, self.LEVEL_CONFIG["info"]).copy()

        # Override icon with event-specific emoji if provided
        if event_type and event_type in self.EVENT_EMOJIS:
            cfg["icon"] = self.EVENT_EMOJIS[event_type]

        # Telegram notification (if bot token and chat ID are configured)
        if self.telegram_bot_token and self.telegram_chat_id:
            self._send_telegram(title, message, cfg, fields)

        # Webhook notification (Discord/Slack/Teams)
        if self.url:
            is_discord = "discord" in self.url

            if is_discord:
                payload = self._build_discord_payload(title, message, cfg, fields)
            else:
                payload = self._build_slack_payload(title, message, cfg, fields)

            try:
                response = requests.post(self.url, json=payload, timeout=5)
                response.raise_for_status()
                logger.info(f"Notification sent: {title}")
            except Exception as e:
                logger.error(f"Failed to send webhook notification: {e}")

    def _build_discord_payload(self, title: str, message: str, cfg: dict, fields: dict[str, str] | None) -> dict:
        ip = fields.pop("IP", None) if fields else None

        description = message
        if ip:
            description += f"\n### `{ip}`"
        if fields:
            description += "\n"
            for name, value in fields.items():
                icon = FIELD_ICONS.get(name, "\u25aa\ufe0f")
                description += f"\n{icon} **{name}:** {value}"

        embed = {
            "title": f"{cfg['icon']}  {title}",
            "description": description,
            "color": cfg["color"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "footer": {"text": self.footer},
        }

        return {"username": self.username, "embeds": [embed]}

    def _build_slack_payload(self, title: str, message: str, cfg: dict, fields: dict[str, str] | None) -> dict:
        hex_color = f"#{cfg['color']:06x}"
        attachment = {
            "color": hex_color,
            "title": f"{cfg['icon']}  {title}",
            "text": message,
            "footer": self.footer,
            "ts": int(datetime.now(timezone.utc).timestamp()),
        }

        if fields:
            attachment["fields"] = [{"title": name, "value": value, "short": True} for name, value in fields.items()]

        return {
            "username": self.username,
            "attachments": [attachment],
        }

    def _send_telegram(self, title: str, message: str, cfg: dict, fields: dict[str, str] | None):
        """Send notification to Telegram using Bot API.

        Args:
            title: Notification title
            message: Message body
            cfg: Level config with icon
            fields: Optional fields dictionary
        """
        # Build message text in Markdown format
        text_parts = [f"*{cfg['icon']} {title}*", "", message]

        # Add fields
        if fields:
            text_parts.append("")
            for name, value in fields.items():
                icon = FIELD_ICONS.get(name, "▪️")
                text_parts.append(f"{icon} *{name}:* {value}")

        # Add footer
        if self.footer:
            text_parts.append("")
            text_parts.append(f"_{self.footer}_")

        telegram_text = "\n".join(text_parts)

        # Send to Telegram API
        telegram_url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": telegram_text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }

        try:
            response = requests.post(telegram_url, json=payload, timeout=5)
            response.raise_for_status()
            logger.info(f"Telegram notification sent: {title}")
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
