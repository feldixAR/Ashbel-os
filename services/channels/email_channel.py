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

_SMTP_READY = bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASS"))


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
    When SMTP is configured, sends via smtplib.
    """
    result = draft_email(recipient_name, recipient_email, body, subject, sender_name)

    if not _SMTP_READY:
        log.info(f"[EmailChannel] SMTP not configured — returning readiness draft for {recipient_email}")
        return result

    # ── Active send path (activates when SMTP credentials are set) ────────────
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        smtp_host = os.getenv("SMTP_HOST")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER")
        smtp_pass = os.getenv("SMTP_PASS")
        from_addr = os.getenv("SMTP_FROM", smtp_user)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{sender_name or 'אשבל'} <{from_addr}>"
        msg["To"]      = recipient_email
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_addr, recipient_email, msg.as_string())

        result.status = ChannelStatus.ACTIVE
        result.meta["sent"] = True
        log.info(f"[EmailChannel] sent to {recipient_email}")
    except Exception as e:
        log.error(f"[EmailChannel] send failed: {e}")
        result.status = ChannelStatus.READINESS
        result.meta["error"] = str(e)

    return result
