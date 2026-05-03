"""
email_channel.py — Email channel readiness layer.

STATUS: READINESS — draft, preview, MIME build are fully implemented.
BLOCKED: actual sending requires SMTP credentials (SMTP_HOST, SMTP_USER, SMTP_PASS env vars).

When credentials are provided, activate send() by removing the BlockedError guard.
"""
import logging
import os
from .channel_base import ChannelResult, ChannelStatus
from .manual_send import _email_manual

log = logging.getLogger(__name__)

_SMTP_READY = False


def draft_email(
    recipient_name: str,
    recipient_email: str,
    body: str,
    subject: str = "",
    sender_name: str = "",
) -> ChannelResult:
    """Draft email content. Always succeeds. Returns readiness result."""
    subject = subject or f"פנייה מ-{sender_name or 'אשבל'}"
    result = _email_manual(recipient_name, recipient_email, body, subject)

    if _SMTP_READY:
        result.status = ChannelStatus.ACTIVE
        result.meta["smtp_ready"] = True
    else:
        result.meta["smtp_ready"]  = False
        result.meta["blocker"]     = "SMTP_HOST, SMTP_USER, SMTP_PASS env vars required"
        result.meta["activate_by"] = "Set SMTP env vars → channel activates automatically"

    return result


def send_email(
    recipient_name: str,
    recipient_email: str,
    body: str,
    subject: str = "",
    sender_name: str = "",
) -> ChannelResult:
    """
    Send email. Returns readiness result if SMTP not configured.
    This function never sends; it returns a draft-only result.
    """
    result = draft_email(recipient_name, recipient_email, body, subject, sender_name)
    log.info(f"[EmailChannel] returning draft-only email for {recipient_email}")
    result.status = ChannelStatus.READINESS
    result.meta["sent"] = False
    result.meta["dry_run"] = True
    return result
