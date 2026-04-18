"""
channel_router.py — Routes outreach to the correct channel service.
Reads business profile for channel priority. Returns best available channel.
"""
import logging
from .channel_base import ChannelResult, ChannelStatus

log = logging.getLogger(__name__)

# Channel priority order from business profile
_DEFAULT_PRIORITY = ["whatsapp", "email", "linkedin", "meta", "sms", "manual"]


def select_channel(lead: dict, profile=None) -> str:
    """
    Select the best channel for a lead based on:
    1. Business profile channel priority
    2. Lead attributes (has phone → whatsapp, has email → email)
    3. Learning data (if available)
    """
    try:
        from skills.learning_skills import get_routing_override
        override = get_routing_override("channel_selection")
        if override:
            return override
    except Exception:
        pass

    if profile is None:
        try:
            from config.business_registry import get_active_business
            profile = get_active_business()
        except Exception:
            pass

    priority = getattr(profile, "outreach_channels", _DEFAULT_PRIORITY) if profile else _DEFAULT_PRIORITY
    phone = lead.get("phone") or lead.get("phone_number")
    email = lead.get("email")

    for ch in priority:
        if ch == "whatsapp" and phone:
            return "whatsapp"
        if ch == "email" and email:
            return "email"
        if ch in ("linkedin", "meta", "facebook", "instagram"):
            return ch
        if ch == "sms" and phone:
            return "sms"

    return "whatsapp" if phone else "email"


def draft_for_channel(
    channel: str,
    lead: dict,
    body: str,
    subject: str = "",
    sender_name: str = "",
) -> ChannelResult:
    """
    Generate a channel-appropriate draft + manual instructions.
    Always returns a usable ChannelResult regardless of credentials.
    """
    name    = lead.get("name") or lead.get("lead_name") or ""
    phone   = lead.get("phone") or lead.get("phone_number") or ""
    email   = lead.get("email") or ""
    profile_url = lead.get("linkedin_url") or ""

    channel = (channel or "whatsapp").lower()

    if channel == "whatsapp":
        from .whatsapp_readiness import draft_whatsapp
        return draft_whatsapp(name, phone, body)

    if channel == "email":
        from .email_channel import draft_email
        return draft_email(name, email, body, subject, sender_name)

    if channel == "linkedin":
        from .linkedin_readiness import draft_linkedin_message
        return draft_linkedin_message(name, profile_url, body, sender_name)

    if channel in ("meta", "facebook", "instagram"):
        from .meta_readiness import draft_meta_message
        return draft_meta_message(name, body, channel)

    # Fallback: manual send for any channel
    from .manual_send import generate_manual_workflow
    return generate_manual_workflow(channel, name, phone or email, body, subject)


def get_channel_status(channel: str) -> dict:
    """Return readiness status for a given channel."""
    import os
    statuses = {
        "whatsapp": {
            "channel": "whatsapp",
            "status":  "active" if (os.getenv("WHATSAPP_ACCESS_TOKEN") and os.getenv("WHATSAPP_PHONE_NUMBER_ID")) else "readiness",
            "blocker": None if os.getenv("WHATSAPP_ACCESS_TOKEN") else "WHATSAPP_ACCESS_TOKEN + WHATSAPP_PHONE_NUMBER_ID",
        },
        "email": {
            "channel": "email",
            "status":  "active" if (os.getenv("SMTP_HOST") and os.getenv("SMTP_USER")) else "readiness",
            "blocker": None if os.getenv("SMTP_HOST") else "SMTP_HOST, SMTP_USER, SMTP_PASS",
        },
        "meta": {
            "channel": "meta",
            "status":  "active" if (os.getenv("META_ACCESS_TOKEN") and os.getenv("META_PAGE_ID")) else "readiness",
            "blocker": None if os.getenv("META_ACCESS_TOKEN") else "META_ACCESS_TOKEN + META_PAGE_ID",
        },
        "linkedin": {
            "channel": "linkedin",
            "status":  "readiness",
            "blocker": "LINKEDIN_ACCESS_TOKEN + manual send required (compliance)",
        },
        "telegram": {
            "channel": "telegram",
            "status":  "active" if os.getenv("TELEGRAM_BOT_TOKEN") else "readiness",
            "blocker": None if os.getenv("TELEGRAM_BOT_TOKEN") else "TELEGRAM_BOT_TOKEN",
            "note":    "operator channel only",
        },
        "manual": {
            "channel": "manual",
            "status":  "active",
            "blocker": None,
        },
    }
    return statuses.get(channel, {"channel": channel, "status": "unknown", "blocker": "not configured"})


def all_channel_statuses() -> list:
    return [get_channel_status(ch) for ch in ["whatsapp", "email", "meta", "linkedin", "telegram", "manual"]]


class ChannelRouter:
    def select(self, lead: dict, profile=None) -> str:
        return select_channel(lead, profile)

    def draft(self, channel: str, lead: dict, body: str, subject: str = "", sender_name: str = "") -> ChannelResult:
        return draft_for_channel(channel, lead, body, subject, sender_name)

    def status(self, channel: str) -> dict:
        return get_channel_status(channel)

    def all_statuses(self) -> list:
        return all_channel_statuses()


channel_router = ChannelRouter()
