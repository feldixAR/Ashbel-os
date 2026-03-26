"""
services/integrations/whatsapp_business.py — Meta WhatsApp Business API (Graph API v19.0).

Environment variables:
    WA_PHONE_NUMBER_ID   — WhatsApp sender phone number ID (from Meta Business)
    WA_ACCESS_TOKEN      — Permanent or system-user access token
    WA_VERIFY_TOKEN      — Webhook verification token (you define it in Meta dashboard)
    WA_API_VERSION       — Graph API version (default: v19.0)

Capabilities:
    send_text(phone, body)            — outbound text message
    send_template(phone, name, lang, components) — pre-approved template message
    verify_webhook(token, challenge)  — GET webhook verification handshake
    parse_event(payload)              — normalize inbound webhook payload → WAEvent

No UI. No sending without env vars — logs warning and returns failure result.
All inbound messages are persisted as MessageModel records.
"""

from __future__ import annotations

import json as _json
import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional

import httpx
import pytz

log = logging.getLogger(__name__)
_IL_TZ = pytz.timezone("Asia/Jerusalem")

_BASE_URL = "https://graph.facebook.com/{version}/{phone_number_id}/messages"


# ── Result contracts ───────────────────────────────────────────────────────────

@dataclass
class WASendResult:
    success:    bool
    message_id: str = ""
    error:      str = ""

    def to_dict(self) -> dict:
        return {"success": self.success, "message_id": self.message_id, "error": self.error}


@dataclass
class WAEvent:
    """Normalised inbound webhook event."""
    event_type:   str           # message | status | unknown
    phone:        str           # sender E.164 without +
    message_id:   str
    body:         str           # text content (empty for non-text)
    timestamp_il: str           # ISO-8601 Asia/Jerusalem
    raw:          dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_type":   self.event_type,
            "phone":        self.phone,
            "message_id":   self.message_id,
            "body":         self.body,
            "timestamp_il": self.timestamp_il,
        }


# ── Client ─────────────────────────────────────────────────────────────────────

class WhatsAppBusinessClient:

    def __init__(self):
        self._phone_id  = os.getenv("WA_PHONE_NUMBER_ID", "")
        self._token     = os.getenv("WA_ACCESS_TOKEN", "")
        self._verify_tk = os.getenv("WA_VERIFY_TOKEN", "ashbel_webhook_token")
        self._version   = os.getenv("WA_API_VERSION", "v19.0")

    @property
    def _configured(self) -> bool:
        return bool(self._phone_id and self._token)

    def _url(self) -> str:
        return _BASE_URL.format(version=self._version,
                                phone_number_id=self._phone_id)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type":  "application/json",
        }

    # ── Outbound ──────────────────────────────────────────────────────────────

    def send_text(self, phone: str, body: str) -> WASendResult:
        """Send a plain-text outbound message."""
        if not self._configured:
            log.warning("[WA_Business] WA_PHONE_NUMBER_ID / WA_ACCESS_TOKEN not set")
            return WASendResult(success=False, error="not_configured")

        payload = {
            "messaging_product": "whatsapp",
            "to":                phone.lstrip("+"),
            "type":              "text",
            "text":              {"body": body},
        }
        return self._post(payload)

    def send_template(self, phone: str, template_name: str,
                      language: str = "he", components: list = None) -> WASendResult:
        """Send a pre-approved WhatsApp template."""
        if not self._configured:
            return WASendResult(success=False, error="not_configured")

        payload = {
            "messaging_product": "whatsapp",
            "to":                phone.lstrip("+"),
            "type":              "template",
            "template": {
                "name":     template_name,
                "language": {"code": language},
                "components": components or [],
            },
        }
        return self._post(payload)

    def mark_read(self, message_id: str) -> bool:
        """Mark an inbound message as read (shows double-blue tick)."""
        if not self._configured:
            return False
        payload = {
            "messaging_product": "whatsapp",
            "status":            "read",
            "message_id":        message_id,
        }
        result = self._post(payload)
        return result.success

    def _post(self, payload: dict) -> WASendResult:
        try:
            resp = httpx.post(
                self._url(),
                headers=self._headers(),
                json=payload,
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
            msg_id = (
                data.get("messages", [{}])[0].get("id", "")
                if data.get("messages") else ""
            )
            log.info(f"[WA_Business] sent message_id={msg_id}")
            return WASendResult(success=True, message_id=msg_id)
        except httpx.HTTPStatusError as e:
            err = f"HTTP {e.response.status_code}: {e.response.text[:300]}"
            log.error(f"[WA_Business] send failed: {err}")
            return WASendResult(success=False, error=err)
        except Exception as e:
            log.error(f"[WA_Business] send error: {e}", exc_info=True)
            return WASendResult(success=False, error=str(e))

    # ── Webhook ───────────────────────────────────────────────────────────────

    def verify_webhook(self, mode: str, token: str, challenge: str) -> Optional[str]:
        """
        Handle Meta's GET verification handshake.
        Returns challenge string on success, None on failure.
        """
        if mode == "subscribe" and token == self._verify_tk:
            log.info("[WA_Business] Webhook verified successfully")
            return challenge
        log.warning(f"[WA_Business] Webhook verification failed: mode={mode}")
        return None

    def parse_events(self, payload: dict) -> List[WAEvent]:
        """
        Parse a WhatsApp webhook POST payload into a list of WAEvent.
        Handles both message and status events.
        """
        events: List[WAEvent] = []
        try:
            for entry in payload.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    # Inbound messages
                    for msg in value.get("messages", []):
                        events.append(self._parse_message(msg, value))
                    # Status updates (delivered, read, failed)
                    for status in value.get("statuses", []):
                        events.append(self._parse_status(status))
        except Exception as e:
            log.error(f"[WA_Business] parse_events error: {e}", exc_info=True)
        return events

    def _parse_message(self, msg: dict, value: dict) -> WAEvent:
        import datetime
        ts_unix = int(msg.get("timestamp", 0))
        ts_il   = (
            datetime.datetime.fromtimestamp(ts_unix, _IL_TZ).isoformat()
            if ts_unix else ""
        )
        body = ""
        if msg.get("type") == "text":
            body = msg.get("text", {}).get("body", "")
        return WAEvent(
            event_type="message",
            phone=msg.get("from", ""),
            message_id=msg.get("id", ""),
            body=body,
            timestamp_il=ts_il,
            raw=msg,
        )

    def _parse_status(self, status: dict) -> WAEvent:
        return WAEvent(
            event_type="status",
            phone=status.get("recipient_id", ""),
            message_id=status.get("id", ""),
            body=status.get("status", ""),
            timestamp_il="",
            raw=status,
        )


# ── Singleton ──────────────────────────────────────────────────────────────────
wa_business = WhatsAppBusinessClient()
