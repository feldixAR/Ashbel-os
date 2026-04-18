"""
meta_readiness.py — Meta (Facebook/Instagram) channel readiness layer.

STATUS: READINESS — content draft + preview implemented.
BLOCKED: execution requires Meta Business API credentials (META_ACCESS_TOKEN, META_PAGE_ID).
"""
import logging
import os
from .channel_base import ChannelResult, ChannelStatus

log = logging.getLogger(__name__)

_META_READY = bool(os.getenv("META_ACCESS_TOKEN") and os.getenv("META_PAGE_ID"))


def draft_meta_message(
    recipient_name: str,
    body: str,
    platform: str = "facebook",
) -> ChannelResult:
    """Draft Facebook/Instagram DM content. Always returns usable draft."""
    platform = platform.lower()
    if platform == "instagram":
        instructions = (
            f"שליחה ב-Instagram:\n"
            f"1. פתח Instagram → חפש {recipient_name}\n"
            f"2. לחץ 'Message'\n"
            f"3. העתק את ההודעה ושלח ✓"
        )
        link = "https://www.instagram.com/direct/new/"
    else:
        instructions = (
            f"שליחה ב-Facebook Messenger:\n"
            f"1. פתח Messenger → חפש {recipient_name}\n"
            f"2. העתק את ההודעה ושלח ✓"
        )
        link = "https://www.messenger.com/"

    meta = {"meta_api_ready": _META_READY}
    if not _META_READY:
        meta["blocker"] = "META_ACCESS_TOKEN + META_PAGE_ID env vars required"

    return ChannelResult(
        channel=platform,
        status=ChannelStatus.READINESS,
        draft=body,
        manual_instructions=instructions,
        deep_link=link,
        copy_text=body,
        meta=meta,
    )


def draft_post(
    caption: str,
    platform: str = "facebook",
    image_prompt: str = "",
) -> ChannelResult:
    """Draft a social media post (page post, not DM)."""
    instructions = (
        f"פרסום ב-{platform.capitalize()}:\n"
        "1. פתח את עמוד העסק\n"
        "2. לחץ 'Create Post' / 'צור פוסט'\n"
        "3. העתק את הטקסט\n"
        "4. הוסף תמונה אם יש\n"
        "5. פרסם ✓"
    )
    meta: dict = {"meta_api_ready": _META_READY}
    if image_prompt:
        meta["image_prompt"] = image_prompt
    if not _META_READY:
        meta["blocker"] = "META_ACCESS_TOKEN + META_PAGE_ID required for auto-posting"

    return ChannelResult(
        channel=f"{platform}_post",
        status=ChannelStatus.READINESS,
        draft=caption,
        manual_instructions=instructions,
        copy_text=caption,
        meta=meta,
    )
