"""
whatsapp_readiness.py — WhatsApp channel readiness layer.

STATUS: READINESS — deep link + draft generation implemented.
BLOCKED: automated sending requires Meta WhatsApp Business API credentials.

The existing outreach_engine._build_whatsapp_link() generates deep links.
This module provides the channel-service contract wrapper.
"""
import logging
import os
import urllib.parse
from .channel_base import ChannelResult, ChannelStatus

log = logging.getLogger(__name__)

_WA_READY = bool(
    os.getenv("WHATSAPP_ACCESS_TOKEN") and os.getenv("WHATSAPP_PHONE_NUMBER_ID")
)


def draft_whatsapp(
    recipient_name: str,
    phone: str,
    body: str,
) -> ChannelResult:
    """Build WhatsApp deep link + draft. Always returns a usable result."""
    phone_clean = "".join(c for c in (phone or "") if c.isdigit() or c == "+")
    if phone_clean and not phone_clean.startswith("+"):
        if phone_clean.startswith("0"):
            phone_clean = "+972" + phone_clean[1:]
        else:
            phone_clean = "+" + phone_clean

    encoded   = urllib.parse.quote(body)
    deep_link = f"https://wa.me/{phone_clean}?text={encoded}" if phone_clean else ""

    instructions = (
        f"שליחה ב-WhatsApp:\n"
        f"1. לחץ על הקישור → {'(' + deep_link[:60] + '...' if len(deep_link) > 60 else deep_link}\n"
        f"2. ההודעה תתמלא אוטומטית\n"
        f"3. לחץ שלח ✓"
    )

    status = ChannelStatus.READINESS
    meta   = {
        "whatsapp_api_ready": _WA_READY,
        "phone_normalized": phone_clean,
    }
    if not _WA_READY:
        meta["blocker"] = "WHATSAPP_ACCESS_TOKEN + WHATSAPP_PHONE_NUMBER_ID required"

    return ChannelResult(
        channel="whatsapp",
        status=status,
        draft=body,
        manual_instructions=instructions,
        deep_link=deep_link,
        copy_text=body,
        meta=meta,
    )
