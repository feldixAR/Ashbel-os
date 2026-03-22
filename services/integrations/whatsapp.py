"""
whatsapp.py — WhatsApp Integration Layer (Batch 5)

Two modes:
    1. wa.me deep link — opens WhatsApp with pre-filled message (no API key)
    2. WhatsApp Business API — real send (requires WHATSAPP_TOKEN env var)
"""

import logging
import urllib.parse
import os
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)

WHATSAPP_TOKEN    = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WA_API_VERSION    = "v19.0"


@dataclass
class WhatsAppMessage:
    to_phone: str
    to_name:  str
    body:     str
    lead_id:  Optional[str] = None


@dataclass
class SendResult:
    success:    bool
    mode:       str
    message_id: Optional[str] = None
    deep_link:  Optional[str] = None
    error:      Optional[str] = None


class WhatsAppService:

    def send(self, msg: WhatsAppMessage) -> SendResult:
        if WHATSAPP_TOKEN and WHATSAPP_PHONE_ID:
            return self._send_via_api(msg)
        return self._send_via_deeplink(msg)

    def build_deep_link(self, phone: str, text: str) -> str:
        clean = _clean_phone(phone)
        return f"https://wa.me/{clean}?text={urllib.parse.quote(text)}"

    def prepare_draft(self, to_name: str, to_phone: str,
                      body: str, lead_id: str = "") -> dict:
        deep_link = self.build_deep_link(to_phone, body) if to_phone else ""
        return {
            "action_type":    "whatsapp_draft",
            "contact_name":   to_name,
            "phone":          to_phone,
            "draft_message":  body,
            "deep_link":      deep_link,
            "lead_id":        lead_id,
            "channel":        "whatsapp",
            "needs_approval": True,
            "next_step":      "approve_and_open" if deep_link else "approve_or_edit",
            "api_ready":      bool(WHATSAPP_TOKEN),
        }

    def _send_via_api(self, msg: WhatsAppMessage) -> SendResult:
        import json, urllib.request, urllib.error
        url  = (f"https://graph.facebook.com/{WA_API_VERSION}"
                f"/{WHATSAPP_PHONE_ID}/messages")
        body = {"messaging_product": "whatsapp",
                "to": _clean_phone(msg.to_phone),
                "type": "text", "text": {"body": msg.body}}
        req = urllib.request.Request(
            url, data=json.dumps(body).encode(), method="POST",
            headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                data   = json.loads(r.read())
                msg_id = data.get("messages", [{}])[0].get("id", "")
                log.info(f"[WhatsApp] sent to {msg.to_phone} id={msg_id}")
                return SendResult(success=True, mode="api", message_id=msg_id)
        except urllib.error.HTTPError as e:
            err = e.read().decode()
            log.error(f"[WhatsApp] API error: {err}")
            return SendResult(success=False, mode="api", error=err)

    def _send_via_deeplink(self, msg: WhatsAppMessage) -> SendResult:
        link = self.build_deep_link(msg.to_phone, msg.body)
        return SendResult(success=True, mode="deeplink", deep_link=link)


def _clean_phone(phone: str) -> str:
    import re
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("0"):
        digits = "972" + digits[1:]
    return digits


whatsapp_service = WhatsAppService()
