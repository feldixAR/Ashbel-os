"""
services/growth/asset_factory.py — Batch 7: Growth Asset Factory.

Generates ready-to-use outreach assets for the committee-selected winner.
No sending occurs here — pure content generation.

Supported asset types:
    whatsapp       — Short Hebrew message with deep-link CTA
    email          — Subject + body draft
    outreach_brief — Structured value-proposition card (JSON-serialisable)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

# ── Audience config ────────────────────────────────────────────────────────────

_AUDIENCE_LABEL: Dict[str, str] = {
    "contractors":        "קבלנים",
    "architects":         "אדריכלים",
    "interior_designers": "מעצבי פנים",
    "general":            "לקוחות עסקיים",
}

_PAIN_POINT: Dict[str, str] = {
    "contractors":        "עיכובי אספקה שמפגרים פרויקטים ועלויות חומר גבוהות",
    "architects":         "קושי למצוא פרופילים בהתאמה אישית ממקור אמין",
    "interior_designers": "מלאי צבעים מוגבל ומינימום הזמנה גבוה מדי",
    "general":            "חיפוש ספק אלומיניום אמין עם שירות מהיר",
}

_OFFER: Dict[str, str] = {
    "contractors":        "אספקה תוך 48 שעות + מחיר קבלני מיוחד",
    "architects":         "פרופילים בהתאמה אישית + ייעוץ טכני חינם",
    "interior_designers": "קטלוג 50+ צבעים וגימורים + מינימום גמיש",
    "general":            "מחיר תחרותי + אספקה מהירה + שירות אישי",
}

_CHANNEL_PHONE: str = "972501234567"   # placeholder — replace via env in production


# ── Output contract ────────────────────────────────────────────────────────────

@dataclass
class GeneratedAsset:
    asset_type:   str    # whatsapp | email | outreach_brief
    channel:      str    # whatsapp | email | linkedin
    audience:     str
    subject:      str = ""          # email only
    content:      str = ""          # rendered text / JSON string
    metadata:     dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "asset_type": self.asset_type,
            "channel":    self.channel,
            "audience":   self.audience,
            "subject":    self.subject,
            "content":    self.content,
            "metadata":   self.metadata,
        }


@dataclass
class AssetBundle:
    opportunity_id:  str
    opportunity_title: str
    audience:        str
    channel:         str
    assets:          List[GeneratedAsset] = field(default_factory=list)

    # Primary asset for quick access
    @property
    def primary(self) -> Optional[GeneratedAsset]:
        """Return the asset matching the opportunity's native channel, else first."""
        for a in self.assets:
            if a.channel == self.channel:
                return a
        return self.assets[0] if self.assets else None

    def to_dict(self) -> dict:
        return {
            "opportunity_id":    self.opportunity_id,
            "opportunity_title": self.opportunity_title,
            "audience":          self.audience,
            "channel":           self.channel,
            "assets":            [a.to_dict() for a in self.assets],
            "primary_asset":     self.primary.to_dict() if self.primary else None,
        }


# ── Generator ──────────────────────────────────────────────────────────────────

def generate_assets(
    opportunity,           # ScoredOpportunity
    research: dict = None, # pipeline research blob (client_profile, market_map)
) -> AssetBundle:
    """
    Generate WhatsApp message, email draft, and outreach brief for a winning opportunity.

    Args:
        opportunity: ScoredOpportunity from the growth committee
        research:    Optional research dict from pipeline (used for personalisation hints)

    Returns:
        AssetBundle with 3 GeneratedAssets ready for persistence
    """
    seg   = opportunity.audience if opportunity.audience in _AUDIENCE_LABEL else "general"
    label = _AUDIENCE_LABEL[seg]
    pain  = _PAIN_POINT[seg]
    offer = _OFFER[seg]
    ch    = opportunity.channel
    title = opportunity.title
    rev   = opportunity.revenue_potential

    assets: List[GeneratedAsset] = [
        _build_whatsapp(seg, label, pain, offer, ch, title),
        _build_email(seg, label, pain, offer, title),
        _build_brief(seg, label, pain, offer, title, rev, opportunity.normalized_score),
    ]

    log.info(
        f"[AssetFactory] Generated {len(assets)} assets for "
        f"opp='{title}' audience={seg} channel={ch}"
    )

    return AssetBundle(
        opportunity_id=opportunity.opp_id,
        opportunity_title=title,
        audience=seg,
        channel=ch,
        assets=assets,
    )


# ── Per-channel builders ───────────────────────────────────────────────────────

def _build_whatsapp(seg: str, label: str, pain: str, offer: str,
                    channel: str, title: str) -> GeneratedAsset:
    content = (
        f"שלום 👋\n\n"
        f"אנחנו באשבל אלומיניום — ספק מוביל לאלומיניום איכותי ל{label}.\n\n"
        f"*הבעיה שאנחנו פותרים:*\n"
        f"_{pain}_\n\n"
        f"*מה אנחנו מציעים:*\n"
        f"✅ {offer}\n\n"
        f"לפרטים ומחיר מיידי 👇\n"
        f"📞 [לחצו לשיחה עכשיו](https://wa.me/{_CHANNEL_PHONE})"
    )
    return GeneratedAsset(
        asset_type="whatsapp",
        channel="whatsapp",
        audience=seg,
        content=content,
        metadata={"length": len(content), "has_cta": True, "opportunity": title},
    )


def _build_email(seg: str, label: str, pain: str, offer: str,
                 title: str) -> GeneratedAsset:
    subject = f"פתרון אלומיניום ל{label} — אשבל אלומיניום"
    body = (
        f"שלום,\n\n"
        f"פניתי אליכם משום שאנחנו מתמחים בעבודה עם {label} "
        f"ומבינים היטב את האתגרים שעמם מתמודדים:\n\n"
        f"  • {pain}\n\n"
        f"*הפתרון שלנו:* {offer}\n\n"
        f"עשרות {label} כבר עובדים איתנו ומדווחים על חיסכון משמעותי "
        f"בעלויות ובזמן.\n\n"
        f"האם תהיו פנויים לשיחה קצרה של 10 דקות השבוע?\n\n"
        f"בברכה,\n"
        f"צוות אשבל אלומיניום\n"
        f"📞 050-000-0000 | אשבל-אלומיניום.co.il"
    )
    return GeneratedAsset(
        asset_type="email",
        channel="email",
        audience=seg,
        subject=subject,
        content=body,
        metadata={"subject": subject, "opportunity": title},
    )


def _build_brief(seg: str, label: str, pain: str, offer: str,
                 title: str, revenue_ils: int, score: int) -> GeneratedAsset:
    import json as _json
    brief = {
        "opportunity_title":  title,
        "target_audience":    label,
        "key_pain_point":     pain,
        "value_proposition":  offer,
        "expected_revenue_ils": revenue_ils,
        "normalized_score":   score,
        "cta":                f"פנייה ל{label} — הצגת הצעת ערך + בקשת פגישה",
        "talking_points": [
            f"אנחנו מכירים את האתגרים שלכם כ{label}",
            "אספקה מהירה ומהימנה — ללא עיכובים",
            "שירות אישי ותמיכה לאורך כל הפרויקט",
            offer,
        ],
    }
    return GeneratedAsset(
        asset_type="outreach_brief",
        channel="internal",
        audience=seg,
        content=_json.dumps(brief, ensure_ascii=False, indent=2),
        metadata={"revenue_ils": revenue_ils, "score": score},
    )
