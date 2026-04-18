"""
manual_send.py — Manual send workflow (fully implemented, no credentials needed).

For every channel, generates:
  - Draft copy to paste
  - Step-by-step send instructions
  - Channel-specific deep link where possible
"""
import urllib.parse
from .channel_base import ChannelResult, ChannelStatus


def generate_manual_workflow(
    channel: str,
    recipient_name: str,
    recipient_contact: str,
    body: str,
    subject: str = "",
) -> ChannelResult:
    """
    Build a complete manual send package for the operator.
    Always succeeds — no credentials or external calls required.
    """
    channel = (channel or "whatsapp").lower()

    if channel == "whatsapp":
        return _whatsapp_manual(recipient_name, recipient_contact, body)
    if channel == "email":
        return _email_manual(recipient_name, recipient_contact, body, subject)
    if channel in ("linkedin", "linkedin_message"):
        return _linkedin_manual(recipient_name, recipient_contact, body)
    if channel in ("facebook", "meta", "instagram"):
        return _meta_manual(recipient_name, recipient_contact, body)
    if channel == "sms":
        return _sms_manual(recipient_name, recipient_contact, body)
    # Fallback: generic manual
    return ChannelResult(
        channel=channel,
        status=ChannelStatus.MANUAL_ONLY,
        draft=body,
        manual_instructions=f"1. פתח {channel}\n2. חפש את {recipient_name}\n3. העתק והדבק את ההודעה\n4. שלח",
        copy_text=body,
    )


def _whatsapp_manual(name: str, phone: str, body: str) -> ChannelResult:
    phone_clean = "".join(c for c in (phone or "") if c.isdigit() or c == "+")
    encoded = urllib.parse.quote(body)
    deep_link = f"https://wa.me/{phone_clean}?text={encoded}" if phone_clean else ""
    instructions = (
        "שלבי שליחה ב-WhatsApp:\n"
        f"1. לחץ על הקישור: {deep_link or 'פתח WhatsApp וחפש ' + name}\n"
        "2. ההודעה תתמלא אוטומטית\n"
        "3. לחץ 'שלח'\n"
        "4. סמן כנשלח במערכת"
    )
    return ChannelResult(
        channel="whatsapp",
        status=ChannelStatus.READINESS,
        draft=body,
        manual_instructions=instructions,
        deep_link=deep_link,
        copy_text=body,
    )


def _email_manual(name: str, email: str, body: str, subject: str) -> ChannelResult:
    encoded_body    = urllib.parse.quote(body)
    encoded_subject = urllib.parse.quote(subject or "פנייה מ-אשבל")
    mailto = f"mailto:{email}?subject={encoded_subject}&body={encoded_body}" if email else ""
    instructions = (
        "שלבי שליחת מייל:\n"
        f"1. פתח לקוח המייל שלך\n"
        f"2. כתוב אל: {email or name}\n"
        f"3. נושא: {subject or 'פנייה'}\n"
        "4. העתק את ההודעה לתוכן המייל\n"
        "5. שלח ✓"
    )
    return ChannelResult(
        channel="email",
        status=ChannelStatus.READINESS,
        draft=body,
        subject=subject,
        manual_instructions=instructions,
        deep_link=mailto,
        copy_text=body,
    )


def _linkedin_manual(name: str, profile_url: str, body: str) -> ChannelResult:
    instructions = (
        "שלבי שליחה ב-LinkedIn (ידנית):\n"
        f"1. פתח פרופיל LinkedIn של {name}\n"
        f"   {profile_url or '(חפש בלינקדאין)'}\n"
        "2. לחץ 'Message' / 'שלח הודעה'\n"
        "3. העתק את ההודעה\n"
        "4. שלח ✓\n"
        "הערה: LinkedIn מגבילה הודעות אוטומטיות — שליחה ידנית נדרשת."
    )
    return ChannelResult(
        channel="linkedin",
        status=ChannelStatus.READINESS,
        draft=body,
        manual_instructions=instructions,
        deep_link=profile_url or "https://www.linkedin.com/messaging/",
        copy_text=body,
    )


def _meta_manual(name: str, contact: str, body: str) -> ChannelResult:
    instructions = (
        "שלבי שליחה ב-Facebook/Instagram:\n"
        f"1. פתח Messenger / Instagram DM\n"
        f"2. חפש {name}\n"
        "3. העתק את ההודעה\n"
        "4. שלח ✓"
    )
    return ChannelResult(
        channel="meta",
        status=ChannelStatus.READINESS,
        draft=body,
        manual_instructions=instructions,
        deep_link="https://www.messenger.com/",
        copy_text=body,
    )


def _sms_manual(name: str, phone: str, body: str) -> ChannelResult:
    phone_clean = "".join(c for c in (phone or "") if c.isdigit() or c == "+")
    sms_link = f"sms:{phone_clean}?body={urllib.parse.quote(body)}" if phone_clean else ""
    instructions = (
        f"שלבי שליחת SMS:\n"
        f"1. פתח אפליקציית הודעות בטלפון\n"
        f"2. שלח אל: {phone or name}\n"
        "3. העתק את ההודעה\n"
        "4. שלח ✓"
    )
    return ChannelResult(
        channel="sms",
        status=ChannelStatus.READINESS,
        draft=body,
        manual_instructions=instructions,
        deep_link=sms_link,
        copy_text=body,
    )
