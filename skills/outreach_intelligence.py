"""
skills/outreach_intelligence.py — Outreach Intelligence Skill
Phase 12: Lead Acquisition OS

Choose best action, channel, timing, and draft messages.
Stateless — all inputs explicit.

CONTRACT:
  choose_action(lead: dict, context: dict) -> ActionChoice
  choose_channel(lead: dict, context: dict) -> str
  choose_timing(lead: dict, context: dict) -> TimingRecommendation
  draft_first_contact(lead: dict, profile: dict) -> MessageDraft
  draft_followup(lead: dict, previous: dict) -> MessageDraft
  draft_comment_reply(comment: dict, lead: dict) -> MessageDraft
  draft_meeting_request(lead: dict, profile: dict) -> MessageDraft
  draft_inbound_response(lead: dict, inbound_text: str) -> MessageDraft
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from skills.israeli_context import get_hebrew_tone, is_good_timing, compliance_hints


def _active_biz() -> str:
    try:
        from config.business_registry import get_active_business
        return get_active_business().name
    except Exception:
        return "החברה שלנו"

def _active_domain() -> str:
    try:
        from config.business_registry import get_active_business
        return get_active_business().domain
    except Exception:
        return "עסק"

def _active_products() -> str:
    try:
        from config.business_registry import get_active_business
        return get_active_business().products
    except Exception:
        return "מוצרים ושירותים"


# ── Data contracts ────────────────────────────────────────────────────────────

@dataclass
class ActionChoice:
    action:      str          # dm | comment_reply | follow_up | meeting_request | wait
    channel:     str          # telegram | whatsapp | email | linkedin_dm | instagram_dm
    reason:      str
    sensitive:   bool = True  # all outreach is sensitive by default
    requires_approval: bool = True


@dataclass
class TimingRecommendation:
    send_at:     str          # e.g. "יום ראשון 09:00"
    reason:      str
    avoid:       list[str] = field(default_factory=list)


@dataclass
class MessageDraft:
    subject:     str
    body:        str
    language:    str   = "he"
    channel:     str   = ""
    action_type: str   = ""
    tone:        str   = "professional"
    requires_approval: bool = True
    notes:       list[str] = field(default_factory=list)


# ── Action choice ─────────────────────────────────────────────────────────────

_ACTION_RULES = [
    # (condition_fn, action, reason)
    (lambda l, c: l.get("is_inbound") and not l.get("last_contact"),
     "dm", "ליד נכנס — מענה ראשון נדרש"),
    (lambda l, c: l.get("is_inbound") and l.get("last_contact"),
     "follow_up", "ליד נכנס — עקוב אחרי מגע קודם"),
    (lambda l, c: l.get("score", 0) >= 70 and not l.get("last_contact"),
     "dm", "ליד חם — פנייה ישירה ראשונה"),
    (lambda l, c: l.get("last_contact") and l.get("attempts", 0) == 1,
     "follow_up", "ניסיון ראשון — שלח follow-up"),
    (lambda l, c: l.get("attempts", 0) >= 2 and l.get("score", 0) >= 60,
     "meeting_request", "ניסיונות מרובים — הצע פגישה"),
    (lambda l, c: l.get("score", 0) >= 40 and c.get("source_type") in ("instagram", "facebook_group"),
     "comment_reply", "מקור ציבורי — תגובה לפוסט מתאימה"),
    (lambda l, c: l.get("score", 0) < 40,
     "wait", "ציון נמוך — שמור למעקב עתידי"),
]


def choose_action(lead: dict[str, Any], context: dict[str, Any] | None = None) -> ActionChoice:
    ctx = context or {}
    for condition, action, reason in _ACTION_RULES:
        try:
            if condition(lead, ctx):
                channel = choose_channel(lead, ctx)
                hints = compliance_hints(channel)
                return ActionChoice(
                    action=action,
                    channel=channel,
                    reason=reason,
                    sensitive=True,
                    requires_approval=(action != "wait"),
                )
        except Exception:
            continue
    return ActionChoice(action="wait", channel="", reason="לא נמצאה פעולה מתאימה", requires_approval=False)


def choose_channel(lead: dict[str, Any], context: dict[str, Any] | None = None) -> str:
    """Select best channel for this lead."""
    ctx = context or {}
    src = lead.get("source_type") or ctx.get("source_type") or ""
    if lead.get("phone"):
        return "whatsapp"
    if src in ("linkedin",):
        return "linkedin_dm"
    if src in ("instagram",):
        return "instagram_dm"
    if lead.get("email"):
        return "email"
    return "telegram"


def choose_timing(lead: dict[str, Any], context: dict[str, Any] | None = None) -> TimingRecommendation:
    """Return Israeli-context-aware timing recommendation."""
    from skills.israeli_context import get_best_send_window, get_holiday_context
    window = get_best_send_window()
    holidays = get_holiday_context()
    avoid = []
    if holidays.get("is_holiday"):
        avoid.append(f"חג/שבת — דחה ל-{holidays.get('next_business_day', 'יום ראשון')}")
    return TimingRecommendation(
        send_at=window,
        reason="שעות עסקים ישראליות מיטביות",
        avoid=avoid,
    )


# ── Message drafts ────────────────────────────────────────────────────────────

def draft_first_contact(lead: dict[str, Any], profile: dict[str, Any] | None = None) -> MessageDraft:
    p = profile or {}
    name    = lead.get("name") or "שלום"
    company = lead.get("company") or ""
    city    = lead.get("city") or ""
    biz     = p.get("name") or _active_biz()
    domain  = _active_domain()
    products = _active_products()
    segment = lead.get("segment") or ""
    tone    = get_hebrew_tone(segment)
    channel = choose_channel(lead)

    location_note = f" ב{city}" if city else ""
    company_note  = f" מ{company}" if company else ""

    body = (
        f"שלום {name},\n\n"
        f"שמי [שם] מ{biz}.\n"
        f"ראיתי את הפעילות שלך{company_note}{location_note} — "
        f"מרשים מאוד!\n\n"
        f"אנחנו מתמחים ב{domain}{location_note}:\n"
        f"✓ {products.split(',')[0].strip() if ',' in products else products}\n"
        f"✓ שירות מותאם אישית לדרישות הספציפיות שלך\n"
        f"✓ ניסיון עם לקוחות בסדר גודל דומה\n\n"
        f"האם יהיה לך נוח להחליף כמה מילים? 5 דקות שיחה יכולות להוביל לפתרון נכון.\n\n"
        f"תודה,\n[שם]\n{biz}"
    )

    # Learning: use best proven template if available (feedback loop)
    try:
        from skills.learning_skills import get_best_template
        learned = get_best_template("first_contact", segment, channel)
        if learned:
            body = learned
    except Exception:
        pass

    return MessageDraft(
        subject=f"היי {name} — פנייה מ{biz}",
        body=body,
        language="he",
        channel=choose_channel(lead),
        action_type="first_contact",
        tone=tone,
        requires_approval=True,
        notes=["הודעה ראשונה — חייבת אישור לפני שליחה"],
    )


def draft_followup(lead: dict[str, Any], previous: dict[str, Any] | None = None) -> MessageDraft:
    name    = lead.get("name") or "שלום"
    days    = previous.get("days_since") or 3 if previous else 3
    biz     = _active_biz()
    segment = lead.get("segment") or ""
    channel = choose_channel(lead)
    body = (
        f"שלום {name},\n\n"
        f"חזרתי אליך בנוגע לפנייה שלי לפני {days} ימים.\n"
        f"מקווה שהכל בסדר.\n\n"
        f"אם עדיין רלוונטי לך, אשמח לשמוע — גם 'לא עכשיו' תשובה בסדר גמור.\n\n"
        f"תודה,\n[שם]\n{biz}"
    )

    # Learning: use best proven follow-up template if available
    try:
        from skills.learning_skills import get_best_template
        learned = get_best_template("follow_up", segment, channel)
        if learned:
            body = learned
    except Exception:
        pass

    return MessageDraft(
        subject=f"מעקב — {name}",
        body=body,
        language="he",
        channel=choose_channel(lead),
        action_type="follow_up",
        tone="light",
        requires_approval=True,
        notes=["follow-up — חייב אישור לפני שליחה"],
    )


def draft_comment_reply(comment: dict[str, Any], lead: dict[str, Any] | None = None) -> MessageDraft:
    post_text = comment.get("text") or ""
    name      = (lead or {}).get("name") or "שלום"
    short_post = post_text[:60] + "..." if len(post_text) > 60 else post_text
    body = (
        f"היי {name},\n"
        f"ראיתי את הפוסט שלך — \"{short_post}\"\n\n"
        f"זה בדיוק הסוג של עניינים ש{_active_biz()} מתמחה בהם.\n"
        f"אפשר לשלוח לך פרטים? (ת'עונה בפרטי אם נוח)"
    )
    return MessageDraft(
        subject="תגובה לפוסט",
        body=body,
        language="he",
        channel=choose_channel(lead or {}),
        action_type="comment_reply",
        tone="friendly",
        requires_approval=True,
        notes=["תגובה לפוסט ציבורי — חייבת אישור"],
    )


def draft_meeting_request(lead: dict[str, Any], profile: dict[str, Any] | None = None) -> MessageDraft:
    name = lead.get("name") or "שלום"
    biz  = (profile or {}).get("name") or _active_biz()
    timing = choose_timing(lead)
    body = (
        f"שלום {name},\n\n"
        f"לאחר מספר התכתבויות, אשמח מאוד לקבוע שיחת היכרות קצרה (15-20 דקות)\n"
        f"בה נוכל לדון ספציפית בצרכים שלך.\n\n"
        f"אני זמין ב{timing.send_at} — מה מתאים לך?\n\n"
        f"תודה,\n[שם]\n{biz}"
    )
    return MessageDraft(
        subject=f"בקשת פגישה — {name}",
        body=body,
        language="he",
        channel=choose_channel(lead),
        action_type="meeting_request",
        tone="professional",
        requires_approval=True,
        notes=["בקשת פגישה — חייבת אישור לפני שליחה", f"זמן מומלץ: {timing.send_at}"],
    )


def should_followup(lead: dict[str, Any]) -> bool:
    """Return True if the lead should receive a follow-up outreach."""
    status = lead.get("status", "")
    attempts = int(lead.get("attempts") or lead.get("outreach_attempts") or 0)
    if status in ("closed", "won", "lost", "unsubscribed"):
        return False
    if status in ("new", "contacted", "hot"):
        return True
    if attempts == 0:
        return True
    return False


def draft_inbound_response(lead: dict[str, Any], inbound_text: str) -> MessageDraft:
    """Draft response to an inbound lead who already left details."""
    name = lead.get("name") or "שלום"
    try:
        from config.business_registry import get_active_business
        biz = get_active_business().name
    except Exception:
        biz = "החברה שלנו"
    short_in = inbound_text[:80] + "..." if len(inbound_text) > 80 else inbound_text
    body = (
        f"שלום {name},\n\n"
        f"תודה שפנית אלינו! קיבלנו את פנייתך:\n"
        f"\"{short_in}\"\n\n"
        f"אחד מהנציגים שלנו יחזור אליך תוך שעות ספורות.\n"
        f"אם דחוף — אתה מוזמן להתקשר ישירות.\n\n"
        f"תודה,\n{biz}"
    )
    return MessageDraft(
        subject=f"קיבלנו את פנייתך, {name}",
        body=body,
        language="he",
        channel=choose_channel(lead),
        action_type="inbound_response",
        tone="warm",
        requires_approval=True,
        notes=["תגובה לליד נכנס — חייבת אישור לפני שליחה"],
    )
