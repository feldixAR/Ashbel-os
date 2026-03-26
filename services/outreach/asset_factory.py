"""
services/outreach/asset_factory.py — Batch 7: Outreach & Execution Engine.

Generates channel-specific message assets (WhatsApp / Email / LinkedIn)
based on audience segment and pain-point context.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List

log = logging.getLogger(__name__)

# ── Audience pain-point registry ───────────────────────────────────────────────

_PAIN_POINTS: dict[str, List[str]] = {
    "contractors": [
        "עיכובי אספקה שמפגרים את הפרויקט",
        "חומרים לא עומדים בתקנות הבנייה",
        "עלויות גבוהות שמכרסמות ברווח",
    ],
    "architects": [
        "קושי למצוא אלומיניום בפרופיל מותאם אישית",
        "ספקים שלא עומדים בלוחות זמנים",
        "חוסר גמישות בהתאמה לדרישות אסתטיות",
    ],
    "interior_designers": [
        "מלאי מוגבל של צבעים וגימורים",
        "שירות לקוחות איטי לפרויקטים דחופים",
        "מינימום הזמנה גבוה מדי",
    ],
    "general": [
        "חיפוש ספק אלומיניום אמין",
        "מחיר תחרותי ללא פשרות על איכות",
        "אספקה מהירה לפרויקטים בלחץ זמן",
    ],
}

# ── Message templates ───────────────────────────────────────────────────────────

_WHATSAPP_TMPL = (
    "שלום {name},\n\n"
    "ראינו שאתם עוסקים ב{audience_label}.\n"
    "אנחנו באשבל אלומיניום מתמחים בפתרון אתגרים כמו:\n"
    "{pain_bullets}\n\n"
    "💡 *ההצעה שלנו:* {offer}\n\n"
    "נשמח לשלוח לכם הצעת מחיר מיידית 👇\n"
    "📞 [לחצו כאן לשיחה](https://wa.me/972XXXXXXXXX)"
)

_EMAIL_TMPL = (
    "שלום {name},\n\n"
    "פניתי אליכם משום שאנחנו באשבל אלומיניום עובדים עם {audience_label} "
    "ומבינים היטב את האתגרים שאיתם מתמודדים:\n"
    "{pain_bullets}\n\n"
    "הפתרון שלנו: {offer}\n\n"
    "האם תהיו פנויים לשיחה קצרה של 10 דקות השבוע?\n\n"
    "בברכה,\nצוות אשבל אלומיניום"
)

_LINKEDIN_TMPL = (
    "שלום {name}, ראיתי את הפרופיל שלכם ונראה שאנחנו יכולים לעזור.\n"
    "אנחנו מספקים אלומיניום איכותי ל{audience_label} עם דגש על {offer}.\n"
    "נשמח להתחבר ולשתף פרטים נוספים."
)

_AUDIENCE_LABELS: dict[str, str] = {
    "contractors":        "קבלנים וחברות בנייה",
    "architects":         "אדריכלים ומעצבי פנים",
    "interior_designers": "מעצבי פנים",
    "general":            "לקוחות עסקיים",
}

_OFFERS: dict[str, str] = {
    "contractors":        "אספקה בתוך 48 שעות עם אחריות על מידות",
    "architects":         "פרופילים בהתאמה אישית עם ייעוץ טכני חינם",
    "interior_designers": "קטלוג צבעים מורחב ומינימום הזמנה גמיש",
    "general":            "מחיר תחרותי ושירות מהיר",
}


# ── Output contract ─────────────────────────────────────────────────────────────

@dataclass
class MessageAsset:
    channel:     str          # whatsapp / email / linkedin
    audience:    str
    subject:     str = ""     # email only
    body:        str = ""
    pain_points: List[str] = field(default_factory=list)
    offer:       str = ""

    def to_dict(self) -> dict:
        return {
            "channel":     self.channel,
            "audience":    self.audience,
            "subject":     self.subject,
            "body":        self.body,
            "pain_points": self.pain_points,
            "offer":       self.offer,
        }


@dataclass
class AssetBundle:
    audience:   str
    assets:     List[MessageAsset] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "audience": self.audience,
            "assets":   [a.to_dict() for a in self.assets],
        }


# ── Factory ─────────────────────────────────────────────────────────────────────

def build_assets(
    audience: str,
    contact_name: str = "לקוח יקר",
    channels: List[str] | None = None,
) -> AssetBundle:
    """
    Generate message assets for the given audience across all requested channels.

    Args:
        audience:     Segment key — contractors / architects / interior_designers / general
        contact_name: Personalisation token (default generic greeting)
        channels:     List of channels to generate; defaults to ["whatsapp", "email", "linkedin"]

    Returns:
        AssetBundle with one MessageAsset per channel
    """
    if channels is None:
        channels = ["whatsapp", "email", "linkedin"]

    seg           = audience if audience in _PAIN_POINTS else "general"
    pain_points   = _PAIN_POINTS[seg]
    offer         = _OFFERS.get(seg, _OFFERS["general"])
    audience_label = _AUDIENCE_LABELS.get(seg, _AUDIENCE_LABELS["general"])
    pain_bullets  = "\n".join(f"• {p}" for p in pain_points)

    assets: List[MessageAsset] = []

    for ch in channels:
        if ch == "whatsapp":
            body = _WHATSAPP_TMPL.format(
                name=contact_name,
                audience_label=audience_label,
                pain_bullets=pain_bullets,
                offer=offer,
            )
            assets.append(MessageAsset(
                channel="whatsapp",
                audience=seg,
                body=body,
                pain_points=pain_points,
                offer=offer,
            ))

        elif ch == "email":
            subject = f"פתרון אלומיניום ל{audience_label} — אשבל אלומיניום"
            body = _EMAIL_TMPL.format(
                name=contact_name,
                audience_label=audience_label,
                pain_bullets=pain_bullets,
                offer=offer,
            )
            assets.append(MessageAsset(
                channel="email",
                audience=seg,
                subject=subject,
                body=body,
                pain_points=pain_points,
                offer=offer,
            ))

        elif ch == "linkedin":
            body = _LINKEDIN_TMPL.format(
                name=contact_name,
                audience_label=audience_label,
                offer=offer,
            )
            assets.append(MessageAsset(
                channel="linkedin",
                audience=seg,
                body=body,
                pain_points=pain_points,
                offer=offer,
            ))

        else:
            log.warning(f"[AssetFactory] Unknown channel '{ch}' — skipped")

    log.info(
        f"[AssetFactory] Built {len(assets)} asset(s) for "
        f"audience={seg} channels={channels}"
    )
    return AssetBundle(audience=seg, assets=assets)
