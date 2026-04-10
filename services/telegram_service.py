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

_TELEGRAM_API          = "https://api.telegram.org/bot{token}/sendMessage"
_TELEGRAM_ANSWER_CBQ   = "https://api.telegram.org/bot{token}/answerCallbackQuery"


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


    def send_approval_request(
        self,
        action:      str,
        preview:     str,
        approval_id: str,
        lead_name:   str = "",
        audience:    str = "",
        channel:     str = "whatsapp",
    ) -> TelegramResult:
        """
        Send an approval message with inline keyboard:
          ✅ אשר  |  ❌ דחה  |  ✏️ ערוך
        callback_data format: "approve:{id}", "deny:{id}", "edit:{id}"
        """
        if not self._token or not self._chat_id:
            return TelegramResult(success=False, error="token/chat_id not set")

        text = (
            f"🔔 *בקשת אישור*\n\n"
            f"👤 ליד: `{lead_name}`\n"
            f"🎯 קהל: `{audience or 'כללי'}`\n"
            f"📡 ערוץ: `{channel}`\n"
            f"📋 פעולה: `{action}`\n\n"
            f"*תצוגה מקדימה:*\n{preview}"
        )
        reply_markup = {
            "inline_keyboard": [[
                {"text": "✅ אשר",  "callback_data": f"approve:{approval_id}"},
                {"text": "❌ דחה",  "callback_data": f"deny:{approval_id}"},
                {"text": "✏️ ערוך", "callback_data": f"edit:{approval_id}"},
            ]]
        }
        url = _TELEGRAM_API.format(token=self._token)
        payload = {
            "chat_id":      self._chat_id,
            "text":         text,
            "parse_mode":   "Markdown",
            "reply_markup": reply_markup,
        }
        try:
            resp = httpx.post(url, json=payload, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            message_id = str(data.get("result", {}).get("message_id", ""))
            log.info(f"[TelegramService] approval request sent msg_id={message_id} approval={approval_id}")
            return TelegramResult(success=True, message_id=message_id)
        except Exception as e:
            log.error(f"[TelegramService] send_approval_request failed: {e}")
            return TelegramResult(success=False, error=str(e))

    def answer_callback(self, callback_query_id: str, text: str = "") -> None:
        """Acknowledge a callback query (removes loading spinner in Telegram)."""
        if not self._token:
            return
        try:
            url = _TELEGRAM_ANSWER_CBQ.format(token=self._token)
            httpx.post(url, json={"callback_query_id": callback_query_id, "text": text}, timeout=5.0)
        except Exception as e:
            log.debug(f"[TelegramService] answer_callback failed: {e}")


# ── Singleton ──────────────────────────────────────────────────────────────────
telegram_service = TelegramService()
