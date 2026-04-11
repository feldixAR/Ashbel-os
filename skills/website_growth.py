"""
skills/website_growth.py — Website Growth Skill
Phase 12: Lead Acquisition OS

Site audit, SEO intelligence, content gaps, landing page improvement,
lead capture review, content drafting, site priority planner.
Deterministic — no AI tokens used (all rule-based).

CONTRACT:
  site_audit(url: str, html: str) -> SiteAudit
  seo_intelligence(audit: SiteAudit, cities: list[str]) -> SeoIntelligence
  content_gap_detection(audit: SiteAudit, segment: str) -> list[ContentGap]
  landing_page_suggestions(audit: SiteAudit) -> list[str]
  lead_capture_review(audit: SiteAudit) -> LeadCaptureReport
  content_draft(topic: str, city: str, product: str) -> str
  priority_planner(audit: SiteAudit, gaps: list[ContentGap]) -> list[PriorityItem]
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any


# ── Data contracts ────────────────────────────────────────────────────────────

@dataclass
class SiteAudit:
    url:               str
    title:             str  = ""
    description:       str  = ""
    h1_count:          int  = 0
    h2_count:          int  = 0
    image_count:       int  = 0
    images_with_alt:   int  = 0
    has_contact_form:  bool = False
    has_phone:         bool = False
    has_whatsapp:      bool = False
    has_testimonials:  bool = False
    has_portfolio:     bool = False
    has_blog:          bool = False
    page_count_estimate: int = 0
    missing_meta:      bool = False
    missing_h1:        bool = False
    slow_signals:      list[str] = field(default_factory=list)
    raw_score:         int  = 0   # 0-100 health score


@dataclass
class SeoIntelligence:
    target_cities:   list[str]
    missing_city_pages: list[str]
    keyword_gaps:    list[str]
    priority_keywords: list[str]
    local_seo_score: float  = 0.0   # 0-1


@dataclass
class ContentGap:
    topic:       str
    type:        str    # blog | city_page | product_page | faq | case_study
    priority:    str    # high | medium | low
    reason:      str
    suggested_title: str = ""


@dataclass
class LeadCaptureReport:
    score:           int     # 0-100
    has_form:        bool
    has_phone:       bool
    has_whatsapp:    bool
    missing_items:   list[str]
    recommendations: list[str]


@dataclass
class PriorityItem:
    title:       str
    type:        str
    priority:    str
    estimated_impact: str   # high | medium | low
    effort:      str        # quick_win | medium | heavy


# ── Site audit ────────────────────────────────────────────────────────────────

def site_audit(url: str, html: str = "") -> SiteAudit:
    """Parse HTML (or use URL-only heuristics) to produce a SiteAudit."""
    audit = SiteAudit(url=url)

    if html:
        audit.title             = _extract_tag(html, "title")
        audit.description       = _extract_meta(html, "description")
        audit.h1_count          = len(re.findall(r"<h1[\s>]", html, re.I))
        audit.h2_count          = len(re.findall(r"<h2[\s>]", html, re.I))
        audit.image_count       = len(re.findall(r"<img[\s>]", html, re.I))
        audit.images_with_alt   = len(re.findall(r'<img[^>]+alt="[^"]{3,}"', html, re.I))
        audit.has_contact_form  = bool(re.search(r"<form", html, re.I))
        audit.has_phone         = bool(re.search(r"05\d[-\s]?\d{3}[-\s]?\d{4}", html))
        audit.has_whatsapp      = bool(re.search(r"whatsapp|וואטסאפ", html, re.I))
        audit.has_testimonials  = bool(re.search(r"testimonial|המלצות|לקוחות אמרו", html, re.I))
        audit.has_portfolio     = bool(re.search(r"portfolio|גלריה|פרויקטים", html, re.I))
        audit.has_blog          = bool(re.search(r"/blog|/articles|/posts|מאמרים", html, re.I))
        audit.page_count_estimate = len(set(re.findall(r'href="(/[^"]{1,60})"', html)))
        audit.missing_meta      = not audit.description
        audit.missing_h1        = audit.h1_count == 0

    audit.raw_score = _compute_audit_score(audit)
    return audit


def _compute_audit_score(a: SiteAudit) -> int:
    score = 0
    if a.title:           score += 15
    if a.description:     score += 10
    if a.h1_count >= 1:   score += 10
    if a.h2_count >= 2:   score += 5
    if a.images_with_alt >= (a.image_count // 2 or 1): score += 5
    if a.has_contact_form: score += 15
    if a.has_phone:        score += 10
    if a.has_whatsapp:     score += 10
    if a.has_testimonials: score += 10
    if a.has_portfolio:    score += 10
    return min(100, score)


# ── SEO intelligence ───────────────────────────────────────────────────────────

_IL_CITIES_TIER1 = [
    "תל אביב", "ירושלים", "חיפה", "ראשון לציון", "פתח תקווה",
    "נתניה", "הרצליה", "רמת גן", "גבעתיים", "מודיעין",
]

_ALUMINUM_KEYWORDS = [
    "אלומיניום", "חלונות אלומיניום", "דלתות אלומיניום", "פרגולת אלומיניום",
    "חלונות כפולים", "חלונות מדרגות", "גדר אלומיניום", "קיר וילון",
    "aluminum windows", "aluminum doors", "pergola aluminum",
]


def seo_intelligence(audit: SiteAudit, cities: list[str] | None = None) -> SeoIntelligence:
    target_cities = cities or _IL_CITIES_TIER1
    # Simulate missing city pages (in real system: cross-check site sitemap)
    missing = [c for c in target_cities if c not in (audit.title + " " + audit.description)]
    keyword_gaps = [kw for kw in _ALUMINUM_KEYWORDS
                    if kw not in (audit.title + " " + audit.description)]
    priority_kws = keyword_gaps[:5]
    local_score = 1.0 - (len(missing) / max(len(target_cities), 1))
    return SeoIntelligence(
        target_cities=target_cities,
        missing_city_pages=missing[:8],
        keyword_gaps=keyword_gaps[:10],
        priority_keywords=priority_kws,
        local_seo_score=round(local_score, 2),
    )


# ── Content gap detection ──────────────────────────────────────────────────────

_SEGMENT_CONTENT_NEEDS: dict[str, list[tuple[str, str, str]]] = {
    # (topic, type, reason)
    "architects": [
        ("חלונות אלומיניום לפרויקטים אדריכליים", "product_page", "דף מוצר ייעודי לאדריכלים"),
        ("גלריית פרויקטים — אדריכלות ואלומיניום", "portfolio", "תיק עבודות מסוננות לפלח"),
        ("מדריך מפרטים טכניים לאדריכלים", "blog", "תוכן מקצועי בעל ערך"),
    ],
    "contractors": [
        ("אלומיניום לבנייה — מחירון ומידות", "product_page", "מידע מקצועי לקבלנים"),
        ("איך לבחור ספק אלומיניום לפרויקט גדול", "blog", "מדריך קבלנים"),
        ("פרויקטים שסיפקנו לקבלנים", "case_study", "הוכחה חברתית"),
    ],
    "homeowners": [
        ("חלונות לבית פרטי — כל מה שצריך לדעת", "blog", "מדריך צרכני בסיסי"),
        ("מחשבון מחיר חלונות", "tool", "lead magnet"),
        ("המלצות לקוחות", "testimonials", "הוכחה חברתית"),
    ],
    "default": [
        ("אודות חברת אשבל אלומיניום", "about_page", "חסר דף אודות מפורט"),
        ("צור קשר — מפה + טופס", "contact_page", "שיפור נגישות"),
        ("שאלות נפוצות", "faq", "מפחית חיכוך לפנייה"),
    ],
}


def content_gap_detection(audit: SiteAudit, segment: str = "default") -> list[ContentGap]:
    needs = _SEGMENT_CONTENT_NEEDS.get(segment, _SEGMENT_CONTENT_NEEDS["default"])
    needs += _SEGMENT_CONTENT_NEEDS["default"]
    seen: set[str] = set()
    gaps: list[ContentGap] = []
    for topic, ctype, reason in needs:
        if topic in seen:
            continue
        seen.add(topic)
        priority = "high" if not audit.has_portfolio and ctype == "portfolio" else \
                   "high" if not audit.has_contact_form and ctype == "contact_page" else \
                   "medium"
        gaps.append(ContentGap(
            topic=topic,
            type=ctype,
            priority=priority,
            reason=reason,
            suggested_title=topic,
        ))
    return gaps


# ── Landing page suggestions ──────────────────────────────────────────────────

def landing_page_suggestions(audit: SiteAudit) -> list[str]:
    tips: list[str] = []
    if not audit.has_phone:
        tips.append("הוסף מספר טלפון בולט בכל עמוד (header ו-footer)")
    if not audit.has_whatsapp:
        tips.append("הוסף כפתור WhatsApp קבוע (floating button)")
    if not audit.has_contact_form:
        tips.append("הוסף טופס יצירת קשר קצר (שם + טלפון + הודעה)")
    if not audit.has_testimonials:
        tips.append("הוסף לפחות 3 המלצות לקוחות עם שם ועיר")
    if not audit.has_portfolio:
        tips.append("הוסף גלריית פרויקטים עם 6–12 תמונות ותיאורים")
    if audit.missing_meta:
        tips.append("הוסף meta description ייחודי לכל עמוד (מגביר CTR בגוגל)")
    if audit.missing_h1:
        tips.append("כל עמוד צריך H1 ברור אחד עם מילת המפתח הראשית")
    if not tips:
        tips.append("האתר נראה טוב! שקול A/B testing על ה-CTA הראשי")
    return tips


# ── Lead capture review ───────────────────────────────────────────────────────

def lead_capture_review(audit: SiteAudit) -> LeadCaptureReport:
    missing: list[str] = []
    recs:    list[str] = []
    score = 0

    if audit.has_contact_form:  score += 35
    else:
        missing.append("טופס יצירת קשר")
        recs.append("הוסף טופס קצר עם 3 שדות בלבד: שם, טלפון, הודעה")

    if audit.has_phone:         score += 25
    else:
        missing.append("מספר טלפון גלוי")
        recs.append("הצג מספר טלפון בולט ב-header")

    if audit.has_whatsapp:      score += 20
    else:
        missing.append("כפתור WhatsApp")
        recs.append("הוסף כפתור WhatsApp עם מסר ברירת מחדל")

    if audit.has_testimonials:  score += 10
    if audit.has_portfolio:     score += 10

    return LeadCaptureReport(
        score=min(100, score),
        has_form=audit.has_contact_form,
        has_phone=audit.has_phone,
        has_whatsapp=audit.has_whatsapp,
        missing_items=missing,
        recommendations=recs,
    )


# ── Content draft ─────────────────────────────────────────────────────────────

def content_draft(topic: str, city: str = "", product: str = "חלונות אלומיניום") -> str:
    """Generate a Hebrew content skeleton for the given topic."""
    city_phrase = f" ב{city}" if city else " בישראל"
    return (
        f"# {topic}\n\n"
        f"## מבוא\n"
        f"[הכנס פסקת פתיחה על {product}{city_phrase}...]\n\n"
        f"## למה לבחור אשבל אלומיניום{city_phrase}?\n"
        f"- ניסיון של שנים בתחום\n"
        f"- חומרי גלם ברמה הגבוהה ביותר\n"
        f"- ליווי מלא מהתכנון ועד ההתקנה\n\n"
        f"## פרויקטים לדוגמה{city_phrase}\n"
        f"[תמונות + תיאורים קצרים]\n\n"
        f"## צור קשר\n"
        f"מעוניין לקבל הצעת מחיר? השאר פרטים ונחזור אליך תוך שעות ספורות."
    )


# ── Priority planner ──────────────────────────────────────────────────────────

def priority_planner(audit: SiteAudit, gaps: list[ContentGap]) -> list[PriorityItem]:
    items: list[PriorityItem] = []

    if not audit.has_contact_form:
        items.append(PriorityItem(
            title="הוסף טופס יצירת קשר",
            type="ux",
            priority="high",
            estimated_impact="high",
            effort="quick_win",
        ))
    if not audit.has_whatsapp:
        items.append(PriorityItem(
            title="הוסף כפתור WhatsApp",
            type="ux",
            priority="high",
            estimated_impact="high",
            effort="quick_win",
        ))
    if audit.missing_meta:
        items.append(PriorityItem(
            title="תיאורי Meta לכל עמוד",
            type="seo",
            priority="high",
            estimated_impact="medium",
            effort="quick_win",
        ))
    for gap in gaps[:4]:
        items.append(PriorityItem(
            title=gap.suggested_title or gap.topic,
            type=gap.type,
            priority=gap.priority,
            estimated_impact="medium",
            effort="medium" if gap.type in ("blog", "case_study") else "quick_win",
        ))
    return items


# ── Private helpers ────────────────────────────────────────────────────────────

def _extract_tag(html: str, tag: str) -> str:
    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", html, re.I | re.S)
    return re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""


def _extract_meta(html: str, name: str) -> str:
    m = re.search(rf'<meta[^>]+name="{name}"[^>]+content="([^"]*)"', html, re.I)
    if not m:
        m = re.search(rf'<meta[^>]+content="([^"]*)"[^>]+name="{name}"', html, re.I)
    return m.group(1).strip() if m else ""
