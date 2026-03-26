"""
TelegramService — sends messages via Telegram Bot API using httpx (sync).

Environment variables required:
    TELEGRAM_BOT_TOKEN  — bot token from @BotFather
    TELEGRAM_CHAT_ID    — target chat/channel ID

Usage:
    from services.telegram_service import telegram_service
    result = telegram_service.send("Hello from AshbelOS")
"""

import logging
import os
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


@dataclass
class TelegramResult:
    success: bool
    message_id: str = ""
    error: str = ""


class TelegramService:

    def __init__(self):
        self._token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self._chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    def send(self, text: str, parse_mode: str = "Markdown") -> TelegramResult:
        """
        Send a text message to the configured chat.
        Returns TelegramResult(success=True, message_id=...) on success.
        """
        if not self._token or not self._chat_id:
            msg = "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set"
            log.warning(f"[TelegramService] {msg}")
            return TelegramResult(success=False, error=msg)

        url = _TELEGRAM_API.format(token=self._token)
        payload = {
            "chat_id":    self._chat_id,
            "text":       text,
            "parse_mode": parse_mode,
        }

        try:
            resp = httpx.post(url, json=payload, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            message_id = str(data.get("result", {}).get("message_id", ""))
            log.info(f"[TelegramService] sent message_id={message_id}")
            return TelegramResult(success=True, message_id=message_id)
        except httpx.HTTPStatusError as e:
            err = f"HTTP {e.response.status_code}: {e.response.text}"
            log.error(f"[TelegramService] {err}")
            return TelegramResult(success=False, error=err)
        except Exception as e:
            log.error(f"[TelegramService] send failed: {e}", exc_info=True)
            return TelegramResult(success=False, error=str(e))


# ── Singleton ──────────────────────────────────────────────────────────────────
telegram_service = TelegramService()
