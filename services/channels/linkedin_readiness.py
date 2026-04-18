"""
linkedin_readiness.py — LinkedIn compliant readiness layer.

STATUS: READINESS — compliant content draft + preview.
BLOCKED: API posting requires LinkedIn Developer credentials (LINKEDIN_ACCESS_TOKEN).
NOTE: LinkedIn restricts automation heavily; manual workflow is the primary path.

Compliance rules applied:
- No bulk messaging
- No automated connection requests
- Content must be professional and non-spammy
- Personalization required
"""
import logging
import os
from .channel_base import ChannelResult, ChannelStatus

log = logging.getLogger(__name__)

_LI_READY = bool(os.getenv("LINKEDIN_ACCESS_TOKEN"))


def draft_linkedin_message(
    recipient_name: str,
    profile_url: str,
    body: str,
    sender_title: str = "",
) -> ChannelResult:
    """
    Draft a compliant LinkedIn direct message.
    Applies personalization and professional tone.
    Manual send workflow always provided.
    """
    # Compliance: ensure personalization
    if recipient_name and recipient_name not in body:
        body = f"שלום {recipient_name},\n\n{body}"

    instructions = (
        f"שליחה ב-LinkedIn (חובה ידנית — LinkedIn מגביל אוטומציה):\n"
        f"1. פתח פרופיל: {profile_url or 'חפש ' + recipient_name + ' ב-LinkedIn'}\n"
        f"2. לחץ 'Message' / 'שלח הודעה'\n"
        f"3. העתק את ההודעה\n"
        f"4. שלח ✓\n\n"
        f"הערת ציות: אין לשלוח את אותה הודעה ל-10+ אנשים — LinkedIn עלולה להגביל את החשבון."
    )

    meta: dict = {
        "linkedin_api_ready": _LI_READY,
        "compliance_note":    "manual send required — LinkedIn restricts automation",
    }
    if not _LI_READY:
        meta["blocker"] = "LINKEDIN_ACCESS_TOKEN required for API posting"

    return ChannelResult(
        channel="linkedin",
        status=ChannelStatus.READINESS,
        draft=body,
        manual_instructions=instructions,
        deep_link=profile_url or "https://www.linkedin.com/messaging/",
        copy_text=body,
        meta=meta,
    )


def draft_linkedin_post(body: str, hashtags: list = None) -> ChannelResult:
    """Draft a LinkedIn page/personal post."""
    tags = " ".join(f"#{t.lstrip('#')}" for t in (hashtags or []))
    full = f"{body}\n\n{tags}".strip() if tags else body

    instructions = (
        "פרסום ב-LinkedIn:\n"
        "1. פתח LinkedIn\n"
        "2. לחץ 'Start a post'\n"
        "3. העתק את הטקסט\n"
        "4. פרסם ✓"
    )
    return ChannelResult(
        channel="linkedin_post",
        status=ChannelStatus.READINESS,
        draft=full,
        manual_instructions=instructions,
        deep_link="https://www.linkedin.com/feed/",
        copy_text=full,
        meta={"linkedin_api_ready": _LI_READY},
    )
